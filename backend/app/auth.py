"""
گیت ورود تک‌کاربره.

این برنامه فقط روی لوکال‌هاست منتشر می‌شود، اما دادهٔ داخلش (کد ملی، شبا،
شماره کارت) حساس است؛ یک رمز جلوی دسترسی اتفاقی را می‌گیرد.

رمز به‌صورت هش argon2 در دیتابیس نگه داشته می‌شود و از داخل خود برنامه
عوض می‌شود. متغیر محیطی فقط برای اولین ورود به‌کار می‌رود: به‌محض اینکه
یک بار با آن وارد شدی، هشش در دیتابیس می‌نشیند و از آن پس مرجع همان است.
"""

import hmac

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.config import settings
from app.services import appsettings

COOKIE_NAME = "pa_session"
_serializer = URLSafeTimedSerializer(settings.secret_key, salt="personal-accounting")
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(db: Session, password: str) -> bool:
    """
    بررسی رمز.

    اگر هنوز رمزی در دیتابیس ثبت نشده، یک بار با مقدار محیطی مقایسه می‌شود
    و در صورت درستی همان‌جا هش شده ذخیره می‌شود — تا دفعهٔ بعد دیگر به
    متغیر محیطی کاری نداشته باشیم.
    """
    password = password or ""
    stored = appsettings.get(db, appsettings.PASSWORD_HASH)

    if stored:
        try:
            _hasher.verify(stored, password)
        except VerifyMismatchError:
            return False
        except Exception:
            return False
        # اگر پارامترهای هش قدیمی شد، بی‌سروصدا تازه‌اش کن
        if _hasher.check_needs_rehash(stored):
            appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(password))
        return True

    # اولین ورود — مهاجرت از متغیر محیطی به دیتابیس
    if settings.app_password and hmac.compare_digest(password, settings.app_password):
        appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(password))
        return True
    return False


def change_password(db: Session, current: str, new: str) -> None:
    """تغییر رمز از داخل برنامه. رمز فعلی باید درست باشد."""
    if not verify_password(db, current):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز فعلی درست نیست.")
    if len(new or "") < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"رمز تازه باید دست‌کم {MIN_PASSWORD_LENGTH} نویسه باشد.",
        )
    if new == current:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمز تازه با رمز فعلی یکی است.")
    appsettings.set(db, appsettings.PASSWORD_HASH, hash_password(new))


def issue_session(response: Response) -> None:
    token = _serializer.dumps({"sub": "owner"})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_session(pa_session: str | None = Cookie(default=None)) -> str:
    if not pa_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "وارد نشده‌اید.")
    try:
        data = _serializer.loads(pa_session, max_age=settings.session_days * 86400)
    except SignatureExpired as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است.") from exc
    except BadSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست نامعتبر است.") from exc
    return data.get("sub", "owner")
