"""
تنظیمات قابل تغییر از داخل خود برنامه.

هرچیزی که کاربر ممکن است بخواهد عوضش کند (رمز ورود، کلید سرویس قیمت،
انتخاب سرویس) در جدول `app_setting` می‌نشیند، نه در فایل محیطی. متغیرهای
محیطی فقط برای «اولین بالا آمدن» به‌کار می‌روند تا برنامه بدون تنظیم دستی
راه بیفتد؛ بعد از آن دیتابیس مرجع است.

در فایل محیطی فقط چیزهایی می‌مانند که زیرساخت‌اند و کاربر با آن‌ها کاری
ندارد: رمز دیتابیس و کلید امضای نشست.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AppSetting

# ---- کلیدها ----
PASSWORD_HASH = "app_password_hash"
MARKET_PROVIDER = "market_provider"
BRSAPI_KEY = "brsapi_key"
NAVASAN_KEY = "navasan_api_key"
MICRO_SPEND = "micro_spend_threshold_rial"
MOM_FACTOR = "mom_alert_factor"

# کلیدهایی که مقدارشان راز است و هرگز کامل به رابط برنمی‌گردد
SECRET_KEYS = {PASSWORD_HASH, BRSAPI_KEY, NAVASAN_KEY}

# مقدار اولیه از متغیر محیطی، فقط تا وقتی کاربر خودش تنظیمش نکرده
_ENV_FALLBACK = {
    MARKET_PROVIDER: lambda: settings.market_provider,
    BRSAPI_KEY: lambda: settings.brsapi_key,
    NAVASAN_KEY: lambda: settings.navasan_api_key,
}


def get(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(AppSetting, key)
    if row is not None and row.value != "":
        return row.value
    if row is not None and row.value == "":
        # کاربر عمداً خالی‌اش کرده — به مقدار محیطی برنگرد
        return ""
    fallback = _ENV_FALLBACK.get(key)
    return fallback() if fallback else default


def set(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def unset(db: Session, key: str) -> None:
    row = db.get(AppSetting, key)
    if row is not None:
        db.delete(row)
        db.commit()


def mask(value: str | None) -> str | None:
    """
    نمایش امن یک کلید — فقط چند نویسهٔ آخر.

    کلید کامل هرگز از سرور بیرون نمی‌رود؛ رابط فقط باید بداند «تنظیم شده».
    """
    if not value:
        return None
    if len(value) <= 6:
        return "•" * len(value)
    return "•" * 6 + value[-4:]


def public_snapshot(db: Session) -> dict:
    """تنظیمات قابل نمایش در رابط — بدون هیچ مقدار رازی."""
    return {
        "market_provider": get(db, MARKET_PROVIDER, "brsapi"),
        "brsapi_key_set": bool(get(db, BRSAPI_KEY)),
        "brsapi_key_hint": mask(get(db, BRSAPI_KEY)),
        "navasan_key_set": bool(get(db, NAVASAN_KEY)),
        "navasan_key_hint": mask(get(db, NAVASAN_KEY)),
        "password_is_custom": db.get(AppSetting, PASSWORD_HASH) is not None,
    }


def bootstrap_from_env(db: Session) -> list[str]:
    """
    یک‌بار مقادیر متغیر محیطی را به دیتابیس منتقل می‌کند.

    از این پس همه‌چیز از داخل خود برنامه تنظیم می‌شود و فایل محیطی فقط
    برای زیرساخت (رمز دیتابیس و کلید امضای نشست) می‌ماند. اگر کاربر
    قبلاً مقداری را در برنامه ثبت کرده باشد، دست‌نخورده می‌ماند.
    """
    moved = []
    for key, source in _ENV_FALLBACK.items():
        if key not in SECRET_KEYS:
            continue
        if db.get(AppSetting, key) is not None:
            continue          # کاربر خودش تنظیمش کرده — دست نزن
        value = (source() or "").strip()
        if value:
            set(db, key, value)
            moved.append(key)
    return moved
