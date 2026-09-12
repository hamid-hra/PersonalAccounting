"""
تست گیت ورود.

جریان: اول «ساخت حساب» (فقط یک بار)، بعد فقط ورود. رمز هش می‌شود، تلاش‌های
ناموفق قفل می‌شوند، و تغییر رمز نشست‌های قبلی را باطل می‌کند.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.auth as auth
from app.auth import (
    change_password,
    hash_password,
    is_setup_required,
    setup_password,
    verify_password,
)
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.services import appsettings


@pytest.fixture(autouse=True)
def _fresh_auth_state(monkeypatch):
    auth.reset_attempts()
    monkeypatch.setattr(auth, "_serializer", None)
    monkeypatch.setattr(settings, "secret_key", "")


@pytest.fixture
def http_db():
    """
    دیتابیس درون‌حافظه‌ای که بین نخ‌ها مشترک است — TestClient درخواست‌ها را در
    نخ دیگری اجرا می‌کند و sqlite:// پیش‌فرض برای هر اتصال دیتابیس تازه می‌سازد.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(http_db):
    app.dependency_overrides[get_db] = lambda: http_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------- منطق
def test_fresh_install_requires_setup(db):
    assert is_setup_required(db) is True
    assert verify_password(db, "anything") is False   # هیچ رمز پیش‌فرضی نیست


def test_setup_stores_argon2_hash_only(db):
    setup_password(db, "first-pass-123")
    stored = appsettings.get(db, appsettings.PASSWORD_HASH)
    assert stored and stored.startswith("$argon2")
    assert "first-pass-123" not in stored
    assert is_setup_required(db) is False
    assert verify_password(db, "first-pass-123") is True
    assert verify_password(db, "wrong") is False


def test_setup_is_one_shot(db):
    setup_password(db, "first-pass-123")
    with pytest.raises(HTTPException) as exc:
        setup_password(db, "another-pass-123")
    assert exc.value.status_code == 409
    assert verify_password(db, "first-pass-123") is True


def test_setup_rejects_short_password(db):
    with pytest.raises(HTTPException):
        setup_password(db, "short")
    assert is_setup_required(db) is True


def test_change_password(db):
    setup_password(db, "first-pass-123")
    change_password(db, "first-pass-123", "second-pass-long")
    assert verify_password(db, "second-pass-long") is True
    assert verify_password(db, "first-pass-123") is False


def test_change_password_requires_correct_current(db):
    setup_password(db, "first-pass-123")
    with pytest.raises(HTTPException) as exc:
        change_password(db, "wrong", "whatever-long")
    assert exc.value.status_code == 400


def test_short_password_rejected(db):
    setup_password(db, "first-pass-123")
    with pytest.raises(HTTPException):
        change_password(db, "first-pass-123", "short")


def test_reset_password_reopens_setup(db):
    setup_password(db, "first-pass-123")
    auth.reset_password(db)
    assert is_setup_required(db) is True


def test_session_secret_is_generated_not_placeholder(db):
    """بدون SECRET_KEY، کلید امضا تصادفی ساخته و ذخیره می‌شود — نه مقدار ثابت."""
    first = auth._session_secret(db)
    assert len(first) >= 40
    assert first == auth._session_secret(db)     # پایدار بین درخواست‌ها


def test_key_is_masked_not_exposed(db):
    """کلید سرویس هرگز کامل از سرور بیرون نمی‌رود."""
    appsettings.set(db, appsettings.BRSAPI_KEY, "SUPERSECRETKEY9999")
    snap = appsettings.public_snapshot(db)
    assert snap["brsapi_key_set"] is True
    assert "SUPERSECRETKEY9999" not in str(snap)
    assert snap["brsapi_key_hint"].endswith("9999")


# ---------------------------------------------------------------- HTTP
def test_http_setup_then_login_only(client):
    assert client.get("/api/auth/status").json() == {"setup_required": True}
    assert client.get("/api/auth/me").status_code == 401
    # تا حساب ساخته نشده، ورود معنی ندارد
    assert client.post("/api/auth/login", json={"password": "x"}).status_code == 409

    r = client.post("/api/auth/setup", json={"password": "first-pass-123"})
    assert r.status_code == 201
    assert client.get("/api/auth/me").status_code == 200          # نشست صادر شد
    assert client.get("/api/auth/status").json() == {"setup_required": False}

    # دفعهٔ دوم ساخت حساب ممکن نیست
    assert client.post("/api/auth/setup", json={"password": "other-pass-123"}).status_code == 409

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"password": "first-pass-123"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_http_lockout_after_repeated_failures(client):
    client.post("/api/auth/setup", json={"password": "first-pass-123"})
    client.post("/api/auth/logout")
    for _ in range(auth.FAILURES_BEFORE_LOCK):
        assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": "first-pass-123"})
    assert r.status_code == 429          # حتی رمز درست هم تا پایان قفل رد می‌شود
    assert "Retry-After" in r.headers


def test_http_password_change_invalidates_other_sessions(client):
    client.post("/api/auth/setup", json={"password": "first-pass-123"})
    stolen = client.cookies.get(auth.COOKIE_NAME)

    r = client.post(
        "/api/auth/password",
        json={"current_password": "first-pass-123", "new_password": "second-pass-long"},
    )
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200        # همین نشست تازه شد

    other = TestClient(app)
    other.cookies.set(auth.COOKIE_NAME, stolen)
    assert other.get("/api/auth/me").status_code == 401         # کوکی قدیمی باطل شد


def test_http_forged_cookie_rejected(client):
    client.post("/api/auth/setup", json={"password": "first-pass-123"})
    client.post("/api/auth/logout")
    client.cookies.set(auth.COOKIE_NAME, "eyJzdWIiOiJvd25lciJ9.forged.signature")
    assert client.get("/api/auth/me").status_code == 401


def test_http_receipts_require_login(client):
    (settings.receipts_dir / ("a" * 64 + ".png")).write_bytes(b"png")
    url = "/api/files/receipts/" + "a" * 64 + ".png"
    assert client.get(url).status_code == 401
    client.post("/api/auth/setup", json={"password": "first-pass-123"})
    assert client.get(url).status_code == 200
    assert client.get("/api/files/receipts/../../etc/passwd").status_code in {404, 401}


def test_http_secrets_never_leave_settings_endpoint(http_db, client):
    client.post("/api/auth/setup", json={"password": "first-pass-123"})
    appsettings.set(http_db, appsettings.BRSAPI_KEY, "SUPERSECRETKEY9999")
    body = client.get("/api/settings").json()
    assert appsettings.PASSWORD_HASH not in body
    assert appsettings.BRSAPI_KEY not in body
    assert "session_secret" not in body
    # و از همین مسیر هم نمی‌شود هش رمز را بازنویسی کرد
    r = client.patch("/api/settings", json={"values": {appsettings.PASSWORD_HASH: "x"}})
    assert r.status_code == 400
    assert verify_password(http_db, "first-pass-123") is True


def test_http_docs_hidden_by_default(client):
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404
