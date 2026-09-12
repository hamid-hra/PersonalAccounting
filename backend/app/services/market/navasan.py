"""
سرویس قیمت نوسان — گزینهٔ دوم.

سهمیهٔ رایگانش ۱۲۰ درخواست در ماه است و اشتراک کاملش ماهی حدود ۳۰ دلار،
پس BrsApi پیش‌فرض است. این ماژول می‌ماند تا اگر کسی کلید نوسان داشت،
با یک متغیر محیطی (`MARKET_PROVIDER=navasan`) بتواند از آن استفاده کند.

نوسان طلای ۲۴ عیار ندارد؛ فهرست اقلامش به همین دلیل کوتاه‌تر است.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from app.config import settings
from app.services.jalali import parse_jalali_date
from app.services.market.base import (
    HistoryPoint,
    ItemDef,
    MarketProvider,
    MarketUnavailable,
    QuotaExhausted,
    QuotaSpec,
    Quote,
)

BASE_URL = "http://api.navasan.tech"

ITEMS = [
    ItemDef("18ayar", "طلای ۱۸ عیار", "gold", "هر گرم", 10),
    ItemDef("usd_sell", "دلار آمریکا", "currency", "هر دلار", 30),
    ItemDef("eur", "یورو", "currency", "هر یورو", 40),
]


class NavasanProvider(MarketProvider):
    name = "navasan"
    label_fa = "نوسان"
    key_setting = "navasan_api_key"
    items = ITEMS

    def quota(self) -> QuotaSpec:
        return QuotaSpec(
            limit=settings.navasan_monthly_quota,
            window="month",
            reserve=settings.navasan_quota_reserve,
            label_fa="در ماه",
        )

    def _get(self, endpoint: str, params: dict) -> dict | list:
        if not self.is_configured():
            raise MarketUnavailable(
                "کلید نوسان ثبت نشده است. در صفحهٔ تنظیمات واردش کن."
            )
        query = urllib.parse.urlencode({**params, "api_key": self.api_key})
        try:
            with urllib.request.urlopen(f"{BASE_URL}/{endpoint}/?{query}", timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise MarketUnavailable("کلید نوسان پذیرفته نشد.") from exc
            if exc.code in (429, 503):
                raise QuotaExhausted("نوسان سهمیه یا نرخ درخواست را رد کرد.") from exc
            raise MarketUnavailable(f"نوسان خطا داد (HTTP {exc.code}).") from exc
        except Exception as exc:
            raise MarketUnavailable(f"دسترسی به نوسان ممکن نشد: {exc}") from exc

    def fetch_latest(self, codes: list[str]) -> list[Quote]:
        payload = self._get("latest", {})
        if not isinstance(payload, dict):
            raise MarketUnavailable("پاسخ نوسان قابل خواندن نبود.")
        out = []
        for code in codes:
            row = payload.get(code)
            if not isinstance(row, dict):
                continue
            price = _to_rial(row.get("value"))
            if price is None:
                continue
            out.append(Quote(code=code, price_rial=price, change_rial=_to_rial(row.get("change"))))
        return out

    def fetch_history(self, code: str, start: date, end: date) -> list[HistoryPoint]:
        payload = self._get(
            "ohlcSearch",
            {"item": code, "start": start.isoformat(), "end": end.isoformat()},
        )
        rows = payload if isinstance(payload, list) else payload.get("data", [])
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            close = _to_rial(row.get("close"))
            if close is None:
                continue
            try:
                day = parse_jalali_date(str(row.get("date", ""))[:10].replace("-", "/"))
            except ValueError:
                continue
            out.append(
                HistoryPoint(
                    day=day,
                    close_rial=close,
                    open_rial=_to_rial(row.get("open")),
                    high_rial=_to_rial(row.get("high")),
                    low_rial=_to_rial(row.get("low")),
                )
            )
        return out


def _to_rial(value) -> int | None:
    """نوسان قیمت را به تومان و به‌صورت رشته می‌دهد."""
    if value in (None, "", "-"):
        return None
    try:
        return int(round(float(str(value).replace(",", "")))) * 10
    except (TypeError, ValueError):
        return None
