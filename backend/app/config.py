"""
پیکربندی.

تنها چیزی که واقعاً از محیط لازم است آدرس دیتابیس است؛ بقیهٔ تنظیمات
(رمز ورود، کلید سرویس قیمت، کلید امضای نشست) در خود دیتابیس می‌نشینند و از
داخل برنامه مدیریت می‌شوند. فایل‌های آپلودشده هم در دیتابیس‌اند، پس برنامه
به دیسک پایدار نیاز ندارد.
"""

import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import quote

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    # متغیر محیطی خالی (مثلاً SESSION_DAYS= بدون مقدار) یعنی «پیش‌فرض»، نه خطا
    model_config = SettingsConfigDict(env_ignore_empty=True)

    # ---- دیتابیس ----
    # یا DATABASE_URL (هر شکلی: postgres://، postgresql://، postgresql+psycopg://)
    # یا اجزای جدا: POSTGRES_HOST / POSTGRES_PORT / POSTGRES_USER /
    # POSTGRES_PASSWORD / POSTGRES_DB — هر کدام که پلتفرم می‌دهد.
    database_url: str = ""
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_user: str = "accounting"
    postgres_password: str = ""
    postgres_db: str = "accounting"

    # کلید امضای نشست. اگر خالی بماند، یک‌بار تصادفی ساخته و در دیتابیس
    # ذخیره می‌شود؛ رمز ورود هم از داخل خود برنامه ساخته می‌شود (بدون پیش‌فرض).
    secret_key: str = ""
    session_days: int = 30
    expose_api_docs: bool = False

    # پورت سرور — بعضی پلتفرم‌ها PORT را خودشان تعیین می‌کنند
    port: int = 8000

    # فقط برای پشتیبان‌های موقت و وارد کردن فایل‌های نسخه‌های قدیمی.
    # لازم نیست پایدار باشد.
    data_dir: Path = Path("/data")

    # ---- سرویس قیمت ارز و طلا ----
    # مقادیر اولیه؛ بعد از اولین اجرا از داخل برنامه (دیتابیس) خوانده می‌شوند.
    market_provider: str = "brsapi"
    brsapi_key: str = ""
    brsapi_daily_quota: int = 1500
    brsapi_quota_reserve: int = 50
    navasan_api_key: str = ""
    navasan_monthly_quota: int = 120
    navasan_quota_reserve: int = 10

    @model_validator(mode="after")
    def _normalize(self) -> "Settings":
        url = self.database_url.strip()
        if url:
            # SQLAlchemy فقط postgresql+psycopg را می‌فهمد
            for prefix in ("postgres://", "postgresql://"):
                if url.startswith(prefix) and not url.startswith("postgresql+"):
                    url = "postgresql+psycopg://" + url[len(prefix):]
                    break
        else:
            url = (
                f"postgresql+psycopg://{quote(self.postgres_user)}:{quote(self.postgres_password)}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        self.database_url = url

        # اگر پوشهٔ داده قابل نوشتن نبود (سرور بدون دیسک)، به پوشهٔ موقت برو
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            (self.data_dir / ".write-test").write_bytes(b"")
            (self.data_dir / ".write-test").unlink()
        except OSError:
            fallback = Path(tempfile.gettempdir()) / "personal-accounting"
            fallback.mkdir(parents=True, exist_ok=True)
            log.warning("پوشهٔ %s قابل نوشتن نیست؛ از %s استفاده می‌شود", self.data_dir, fallback)
            self.data_dir = fallback
        return self

    @property
    def statements_dir(self) -> Path:
        return self.data_dir / "statements"

    @property
    def receipts_dir(self) -> Path:
        return self.data_dir / "receipts"

    @property
    def wishlist_dir(self) -> Path:
        return self.data_dir / "wishlist"

    @property
    def static_dir(self) -> Path | None:
        """خروجی ساخته‌شدهٔ فرانت — اگر کنار بک‌اند باشد، خودِ سرور آن را سرو می‌کند."""
        candidate = Path(os.environ.get("STATIC_DIR", "/srv/static"))
        return candidate if (candidate / "index.html").is_file() else None


settings = Settings()
