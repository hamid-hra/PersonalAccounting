"""
سرویس قیمت BrsApi.ir — پیش‌فرض برنامه.

چرا این به‌جای نوسان: سهمیهٔ رایگانش **۱۵۰۰ درخواست در روز** است (نوسان:
۱۲۰ در ماه با اشتراک ۳۰ دلاری)، طلای ۲۴ عیار دارد که نوسان ندارد، و
درصد تغییر را آماده می‌دهد.

پاسخ واقعی سرویس:
    {"symbol":"IR_GOLD_18K","price":6214700,"change_percent":-1.53,"unit":"تومان"}

نکتهٔ مهم: قیمت‌ها **به تومان** می‌آیند ولی داخل برنامه همه‌چیز ریال است.
واحد از خودِ فیلد `unit` خوانده می‌شود، نه حدس — اگر روزی سرویس واحدش را
عوض کند، عدد ده برابر غلط نمی‌شود.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from app.config import settings
from app.services.jalali import parse_jalali_date, to_jalali_str
from app.services.market.base import (
    HistoryPoint,
    ItemDef,
    MarketProvider,
    MarketUnavailable,
    QuotaExhausted,
    QuotaSpec,
    Quote,
)

BASE_URL = "https://Api.BrsApi.ir/Market/Gold_Currency_Pro.php"

ITEMS = [
    ItemDef("IR_GOLD_18K", "طلای ۱۸ عیار", "gold", "هر گرم", 10),
    ItemDef("IR_GOLD_24K", "طلای ۲۴ عیار", "gold", "هر گرم", 20),
    ItemDef("USD", "دلار آمریکا", "currency", "هر دلار", 30),
    ItemDef("EUR", "یورو", "currency", "هر یورو", 40),
]


def to_rial(price, unit: str | None) -> int | None:
    """
    قیمت + واحدِ اعلام‌شده → ریال صحیح.

    سرویس «تومان» می‌دهد؛ ضریب از روی همان رشته تعیین می‌شود تا اگر روزی
    عوض شد، عدد بی‌صدا ده برابر غلط نشود.
    """
    if price in (None, "", "-"):
        return None
    try:
        value = float(str(price).replace(",", ""))
    except (TypeError, ValueError):
        return None
    text = (unit or "").strip()
    if "ریال" in text:
        factor = 1
    elif "تومان" in text or not text:
        factor = 10
    else:
        factor = 10  # پیش‌فرض سرویس تومان است
    return int(round(value * factor))


class BrsApiProvider(MarketProvider):
    name = "brsapi"
    label_fa = "BrsApi (رایگان)"
    key_setting = "brsapi_key"
    items = ITEMS

    def quota(self) -> QuotaSpec:
        return QuotaSpec(
            limit=settings.brsapi_daily_quota,
            window="day",
            reserve=settings.brsapi_quota_reserve,
            label_fa="در روز",
        )

    # ---------------------------------------------------------------- شبکه
    def _get(self, params: dict) -> dict | list:
        if not self.is_configured():
            raise MarketUnavailable(
                "کلید BrsApi ثبت نشده است. یک کلید رایگان از "
                "api.brsapi.ir بگیر و در صفحهٔ تنظیمات واردش کن."
            )
        url = f"{BASE_URL}?{urllib.parse.urlencode({**params, 'key': self.api_key})}"
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise MarketUnavailable("کلید BrsApi پذیرفته نشد.") from exc
            if exc.code == 429:
                raise QuotaExhausted("BrsApi سقف درخواست روزانه را رد کرد.") from exc
            raise MarketUnavailable(f"BrsApi خطا داد (HTTP {exc.code}).") from exc
        except Exception as exc:
            raise MarketUnavailable(f"دسترسی به BrsApi ممکن نشد: {exc}") from exc

        # سرویس خطاها را با کد ۲۰۰ و بدنهٔ JSON هم برمی‌گرداند
        if isinstance(payload, dict) and payload.get("successful") is False:
            message = payload.get("message_error", "خطای نامشخص")
            if payload.get("code_http") == 401:
                raise MarketUnavailable(f"کلید BrsApi پذیرفته نشد: {message}")
            raise MarketUnavailable(f"BrsApi: {message}")
        return payload

    # ---------------------------------------------------------------- قیمت
    def fetch_latest(self, codes: list[str]) -> list[Quote]:
        """همهٔ اقلام با یک درخواست — سرویس کل جدول را یکجا می‌دهد."""
        payload = self._get({})
        wanted = set(codes)
        out: list[Quote] = []

        sections = payload.values() if isinstance(payload, dict) else [payload]
        for section in sections:
            if not isinstance(section, list):
                continue
            for row in section:
                if not isinstance(row, dict) or row.get("symbol") not in wanted:
                    continue
                price = to_rial(row.get("price"), row.get("unit"))
                if price is None:
                    continue
                out.append(
                    Quote(
                        code=row["symbol"],
                        price_rial=price,
                        change_percent=_as_float(row.get("change_percent")),
                        change_rial=to_rial(row.get("change_value"), row.get("unit")),
                        as_of=_jalali_or_today(row.get("date")),
                    )
                )
        return out

    def fetch_history(self, code: str, start: date, end: date) -> list[HistoryPoint]:
        """تاریخچهٔ روزانه — یک درخواست برای کل بازه (history=2)."""
        payload = self._get(
            {
                "history": 2,
                "symbol": code,
                "date_start": to_jalali_str(start).replace("/", "-"),
                "date_end": to_jalali_str(end).replace("/", "-"),
            }
        )
        rows = payload if isinstance(payload, list) else _first_list(payload)
        out: list[HistoryPoint] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            day = _jalali_or_today(row.get("date"), fallback=None)
            price = to_rial(row.get("price") or row.get("close"), row.get("unit"))
            if day is None or price is None:
                continue
            out.append(
                HistoryPoint(
                    day=day,
                    close_rial=price,
                    open_rial=to_rial(row.get("open"), row.get("unit")),
                    high_rial=to_rial(row.get("high"), row.get("unit")),
                    low_rial=to_rial(row.get("low"), row.get("unit")),
                )
            )
        return out


def _as_float(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _first_list(payload) -> list:
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                return value
    return []


def _jalali_or_today(value, fallback: date | None = None) -> date | None:
    """تاریخ سرویس جلالی است («1404/02/28»)."""
    if not value:
        return fallback if fallback is not None else date.today()
    try:
        return parse_jalali_date(str(value).replace("-", "/"))
    except ValueError:
        return fallback if fallback is not None else date.today()
