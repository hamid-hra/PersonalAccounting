from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # متغیر محیطی خالی (مثلاً SESSION_DAYS= بدون مقدار) یعنی «پیش‌فرض»، نه خطا
    model_config = SettingsConfigDict(env_ignore_empty=True)

    database_url: str = "postgresql+psycopg://accounting:accounting@db:5432/accounting"
    app_password: str = "change-me-please"
    secret_key: str = "insecure-dev-key"
    session_days: int = 30
    data_dir: Path = Path("/data")

    # ---- سرویس قیمت ارز و طلا ----
    # brsapi رایگان است (۱۵۰۰ درخواست در روز) و طلای ۲۴ عیار هم دارد؛
    # navasan فقط ۱۲۰ درخواست در ماه می‌دهد و اشتراک کاملش هزینه دارد.
    market_provider: str = "brsapi"
    brsapi_key: str = ""
    brsapi_daily_quota: int = 1500
    brsapi_quota_reserve: int = 50

    # ---- نوسان (گزینهٔ دوم) ----
    # بدون کلید، بخش بازار خاموش می‌ماند و بقیهٔ برنامه کامل کار می‌کند.
    navasan_api_key: str = ""
    # پلن رایگان: ۱۲۰ درخواست در ماه
    navasan_monthly_quota: int = 120
    # ذخیرهٔ احتیاطی — چند درخواست همیشه برای مواقع لازم کنار گذاشته می‌شود
    navasan_quota_reserve: int = 10

    @property
    def statements_dir(self) -> Path:
        return self.data_dir / "statements"

    @property
    def receipts_dir(self) -> Path:
        return self.data_dir / "receipts"


settings = Settings()
settings.statements_dir.mkdir(parents=True, exist_ok=True)
settings.receipts_dir.mkdir(parents=True, exist_ok=True)
