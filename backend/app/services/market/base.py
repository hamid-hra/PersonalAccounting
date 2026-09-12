"""
قرارداد مشترک سرویس‌های قیمت.

افزودن یک سرویس تازه = یک فایل در همین پوشه که `MarketProvider` را پیاده کند
و خودش را ثبت کند. بقیهٔ برنامه تغییر نمی‌کند.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class ItemDef:
    """یک قلم قابل پیگیری، همان‌طور که این سرویس صدایش می‌زند."""

    code: str          # نماد در همین سرویس، مثلاً IR_GOLD_18K
    label_fa: str
    kind: str          # gold | currency | coin
    unit_fa: str
    sort_order: int = 100


@dataclass
class Quote:
    """قیمت لحظه‌ای یک قلم."""

    code: str
    price_rial: int
    change_percent: float | None = None
    change_rial: int | None = None
    as_of: date | None = None


@dataclass
class HistoryPoint:
    day: date
    close_rial: int
    open_rial: int | None = None
    high_rial: int | None = None
    low_rial: int | None = None


@dataclass
class QuotaSpec:
    """سقف مجاز این سرویس و بازهٔ شمارش آن."""

    limit: int
    window: str          # "day" یا "month"
    reserve: int = 0
    label_fa: str = ""


class MarketProvider(ABC):
    name: str
    label_fa: str
    # نام تنظیمی که کلید این سرویس در آن نگه داشته می‌شود
    key_setting: str
    items: list[ItemDef] = []

    def __init__(self, api_key: str = "") -> None:
        # کلید از تنظیمات برنامه می‌آید، نه از محیط — تا کاربر بتواند از
        # داخل خود برنامه عوضش کند.
        self.api_key = api_key or ""

    @abstractmethod
    def quota(self) -> QuotaSpec: ...

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def fetch_latest(self, codes: list[str]) -> list[Quote]:
        """قیمت امروزِ همهٔ اقلام — باید با **یک** درخواست انجام شود."""

    @abstractmethod
    def fetch_history(self, code: str, start: date, end: date) -> list[HistoryPoint]:
        """تاریخچهٔ روزانهٔ یک قلم — یک درخواست برای کل بازه."""


class QuotaExhausted(RuntimeError):
    """سهمیه تمام شده — درخواست عمداً زده نشد."""


class MarketUnavailable(RuntimeError):
    """کلید تنظیم نشده یا سرویس در دسترس نیست."""
