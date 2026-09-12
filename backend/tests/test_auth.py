"""
تست گیت ورود و تغییر رمز.

رمز باید در دیتابیس هش شود و از داخل خود برنامه قابل تغییر باشد؛ متغیر
محیطی فقط برای اولین ورود است.
"""

import pytest
from fastapi import HTTPException

from app.auth import change_password, hash_password, verify_password
from app.config import settings
from app.services import appsettings


def test_first_login_uses_env_then_stores_hash(db, monkeypatch):
    """اولین ورود با مقدار محیطی، بعد هش در دیتابیس می‌نشیند."""
    monkeypatch.setattr(settings, "app_password", "bootstrap-pass")
    assert appsettings.get(db, appsettings.PASSWORD_HASH) is None

    assert verify_password(db, "bootstrap-pass") is True

    stored = appsettings.get(db, appsettings.PASSWORD_HASH)
    assert stored and stored.startswith("$argon2")
    assert "bootstrap-pass" not in stored  # رمز خام ذخیره نشده


def test_wrong_password_rejected(db, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "bootstrap-pass")
    assert verify_password(db, "wrong") is False


def test_db_password_wins_over_env(db, monkeypatch):
    """بعد از ثبت رمز در برنامه، مقدار محیطی دیگر کار نمی‌کند."""
    monkeypatch.setattr(settings, "app_password", "old-env-pass")
    appsettings.set(db, appsettings.PASSWORD_HASH, hash_password("new-app-pass"))

    assert verify_password(db, "new-app-pass") is True
    assert verify_password(db, "old-env-pass") is False


def test_change_password(db, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "first-pass")
    verify_password(db, "first-pass")          # مهاجرت به دیتابیس

    change_password(db, "first-pass", "second-pass-long")
    assert verify_password(db, "second-pass-long") is True
    assert verify_password(db, "first-pass") is False


def test_change_password_requires_correct_current(db, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "first-pass")
    verify_password(db, "first-pass")
    with pytest.raises(HTTPException) as exc:
        change_password(db, "wrong", "whatever-long")
    assert exc.value.status_code == 400


def test_short_password_rejected(db, monkeypatch):
    monkeypatch.setattr(settings, "app_password", "first-pass")
    verify_password(db, "first-pass")
    with pytest.raises(HTTPException):
        change_password(db, "first-pass", "short")


def test_key_is_masked_not_exposed(db):
    """کلید سرویس هرگز کامل از سرور بیرون نمی‌رود."""
    appsettings.set(db, appsettings.BRSAPI_KEY, "SUPERSECRETKEY9999")
    snap = appsettings.public_snapshot(db)
    assert snap["brsapi_key_set"] is True
    assert "SUPERSECRETKEY9999" not in str(snap)
    assert snap["brsapi_key_hint"].endswith("9999")
