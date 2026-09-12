"""
گیت ورود تک‌کاربره.

دادهٔ داخل برنامه (کد ملی، شبا، شماره کارت) حساس است؛ یک رمز جلوی دسترسی را
می‌گیرد. جریان کار:

  • اولین بار که برنامه بالا می‌آید هیچ رمزی وجود ندارد → صفحهٔ «ساخت حساب»
    نشان داده می‌شود و کاربر رمزش را می‌گذارد (`setup_password`).
  • از آن به بعد فقط ورود با همان رمز ممکن است؛ راه دیگری برای ساخت حساب
    نیست. اگر رمز فراموش شد: `python -m app.reset_password` داخل کانتینر.

رمز به‌صورت هش argon2id در دیتابیس می‌ماند. هیچ رمز پیش‌فرض یا متغیر
محیطی‌ای وجود ندارد که بشود با آن وارد شد.

نشست: کوکی امضاشده (itsdangerous). کلید امضا اگر در محیط داده نشده باشد،
یک‌بار تصادفی ساخته و در دیتابیس ذخیره می‌شود — نه یک مقدار پیش‌فرضِ
قابل‌حدس. توکن نشست به هش رمز گره خورده، پس با عوض شدن رمز همهٔ
نشست‌های قبلی (مثلاً کوکی دزدیده‌شده) باطل می‌شوند.
"""

import hashlib
import secrets
import threading
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.services import appsettings

COOKIE_NAME = "pa_session"
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# مقادیری که یعنی «کلید امضا تنظیم نشده» — با این‌ها هرگز امضا نمی‌کنیم
_PLACEHOLDER_SECRETS = {"", "insecure-dev-key", "change-me-to-a-long-random-string"}


# ---------------------------------------------------------------- رمز
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def is_setup_required(db: Session) -> bool:
    """تا وقتی رمزی ثبت نشده، فقط صفحهٔ ساخت حساب در دسترس است."""
    return not appsettings.get(db, appsettings.PASSWORD_HASH)


def _validate_new_password(new: str) -> None:
    new = new or ""
    if len(new) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"رمز باید دست‌کم {MIN_PASSWORD_LENGTH} نویسه باشد.",
        )
    if len(new) > MAX_PASSWORD_LENGTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز بیش از حد بلند است.")


def setup_password(db: Session, password: str) -> None:
    """ساخت حساب — فقط یک بار، وقتی هنوز هیچ رمزی ثبت نشده."""
    if not is_setup_required(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "حساب قبلاً ساخته شده؛ وارد شو.")
    _validate_new_password(password)
    appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(password))


def verify_password(db: Session, password: str) -> bool:
    stored = appsettings.get(db, appsettings.PASSWORD_HASH)
    if not stored:
        return False
    try:
        _hasher.verify(stored, password or "")
    except VerifyMismatchError:
        return False
    except Exception:
        return False
    # اگر پارامترهای هش قدیمی شد، بی‌سروصدا تازه‌اش کن
    if _hasher.check_needs_rehash(stored):
        appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(password))
    return True


def change_password(db: Session, current: str, new: str) -> None:
    """تغییر رمز از داخل برنامه. رمز فعلی باید درست باشد."""
    if not verify_password(db, current):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز فعلی درست نیست.")
    _validate_new_password(new)
    if new == current:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز تازه با رمز فعلی یکی است.")
    appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(new))


def reset_password(db: Session) -> None:
    """حذف رمز → دفعهٔ بعد صفحهٔ ساخت حساب می‌آید. فقط از خط فرمان."""
    appsettings.unset(db, appsettings.PASSWORD_HASH)


# ---------------------------------------------------------------- محدودیت تلاش
# جلوی حدس زدن رمز با اسکریپت را می‌گیرد: بعد از چند خطای پشت‌سرهم، هر
# تلاش بعدی مدتی قفل می‌شود و مدت قفل با هر خطا دو برابر می‌شود.
FAILURES_BEFORE_LOCK = 5
LOCK_BASE_SECONDS = 30
LOCK_MAX_SECONDS = 3600

_attempts: dict[str, tuple[int, float]] = {}   # کلید → (تعداد خطا، قفل تا)
_attempts_lock = threading.Lock()


def client_key(request: Request) -> str:
    # پشت nginx آی‌پی واقعی در هدر می‌آید؛ nginx خودش این هدر را می‌گذارد
    forwarded = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "?")
    return ip


def check_not_locked(key: str) -> None:
    with _attempts_lock:
        failures, locked_until = _attempts.get(key, (0, 0.0))
    remaining = int(locked_until - time.monotonic())
    if remaining > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"تلاش‌های ناموفق زیاد بود؛ {remaining} ثانیه دیگر دوباره امتحان کن.",
            headers={"Retry-After": str(remaining)},
        )


def record_failure(key: str) -> None:
    with _attempts_lock:
        failures, _ = _attempts.get(key, (0, 0.0))
        failures += 1
        locked_until = 0.0
        if failures >= FAILURES_BEFORE_LOCK:
            wait = min(LOCK_BASE_SECONDS * 2 ** (failures - FAILURES_BEFORE_LOCK), LOCK_MAX_SECONDS)
            locked_until = time.monotonic() + wait
        _attempts[key] = (failures, locked_until)


def record_success(key: str) -> None:
    with _attempts_lock:
        _attempts.pop(key, None)


def reset_attempts() -> None:
    """برای تست‌ها."""
    with _attempts_lock:
        _attempts.clear()


# ---------------------------------------------------------------- نشست
SESSION_SECRET = "session_secret"
_serializer: URLSafeTimedSerializer | None = None
_serializer_lock = threading.Lock()


def _session_secret(db: Session) -> str:
    if settings.secret_key not in _PLACEHOLDER_SECRETS:
        return settings.secret_key
    stored = appsettings.get(db, SESSION_SECRET)
    if stored:
        return stored
    generated = secrets.token_urlsafe(48)
    appsettings.set(db, SESSION_SECRET, generated)
    return generated


def _get_serializer(db: Session) -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        with _serializer_lock:
            if _serializer is None:
                _serializer = URLSafeTimedSerializer(_session_secret(db), salt="personal-accounting")
    return _serializer


def _password_version(db: Session) -> str:
    """اثر انگشت هش فعلی؛ در توکن می‌نشیند تا تغییر رمز نشست‌های قبلی را باطل کند."""
    stored = appsettings.get(db, appsettings.PASSWORD_HASH) or ""
    return hashlib.sha256(stored.encode()).hexdigest()[:16]


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",")[0].strip().lower() == "https"


def issue_session(db: Session, request: Request, response: Response) -> None:
    token = _get_serializer(db).dumps({"sub": "owner", "v": _password_version(db)})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        # پشت HTTPS کوکی فقط روی اتصال امن فرستاده می‌شود
        secure=_is_https(request),
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_session(
    db: Session = Depends(get_db),
    pa_session: str | None = Cookie(default=None),
) -> str:
    if not pa_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "وارد نشده‌اید.")
    try:
        data = _get_serializer(db).loads(pa_session, max_age=settings.session_days * 86400)
    except SignatureExpired as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است.") from exc
    except BadSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست نامعتبر است.") from exc
    if data.get("v") != _password_version(db):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "رمز عوض شده؛ دوباره وارد شو.")
    return data.get("sub", "owner")
