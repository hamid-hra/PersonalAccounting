"""تبدیل و محاسبات تاریخ جلالی."""

import re
from datetime import date, datetime

import jdatetime

from app.services.normalize import fa_digits

MONTH_NAMES_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]

_DT_RE = re.compile(
    r"(?P<y>1[34]\d{2})[/\-](?P<m>\d{1,2})[/\-](?P<d>\d{1,2})"
    r"(?:[ T]+(?P<hh>\d{1,2}):(?P<mm>\d{2})(?::(?P<ss>\d{2}))?)?"
)


def parse_jalali(value: str) -> tuple[datetime, str]:
    """
    «1405/06/10 18:42:09» → (datetime میلادی، رشتهٔ جلالیِ یکدست)

    ارقام فارسی و جداکنندهٔ «-» هم پذیرفته می‌شود.
    """
    m = _DT_RE.search(fa_digits(value or ""))
    if not m:
        raise ValueError(f"تاریخ جلالی نامعتبر: {value!r}")
    y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
    hh, mi, ss = int(m["hh"] or 0), int(m["mm"] or 0), int(m["ss"] or 0)
    greg = jdatetime.datetime(y, mo, d, hh, mi, ss).togregorian()
    return greg, f"{y:04d}/{mo:02d}/{d:02d} {hh:02d}:{mi:02d}:{ss:02d}"


def parse_jalali_date(value: str) -> date:
    """«1404/07/06» → date میلادی."""
    m = _DT_RE.search(fa_digits(value or ""))
    if not m:
        raise ValueError(f"تاریخ جلالی نامعتبر: {value!r}")
    return jdatetime.date(int(m["y"]), int(m["m"]), int(m["d"])).togregorian()


def jalali_parts(value: str) -> tuple[int, int, int]:
    """«1405/06/10 ...» → (1405, 6, 10)"""
    m = _DT_RE.search(fa_digits(value or ""))
    if not m:
        raise ValueError(f"تاریخ جلالی نامعتبر: {value!r}")
    return int(m["y"]), int(m["m"]), int(m["d"])


def to_jalali_str(value: date | datetime) -> str:
    """date/datetime میلادی → «1405/06/10»"""
    if isinstance(value, datetime):
        value = value.date()
    j = jdatetime.date.fromgregorian(date=value)
    return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"


def today_jalali_parts() -> tuple[int, int, int]:
    j = jdatetime.date.today()
    return j.year, j.month, j.day


def month_length(year: int, month: int) -> int:
    """تعداد روزهای یک ماه جلالی (اسفند در سال کبیسه ۳۰ روز است)."""
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def add_months(year: int, month: int, day: int, count: int) -> tuple[int, int, int]:
    """
    n ماه جلالی جلو می‌رود و روز را به آخر ماه می‌چسباند اگر آن ماه کوتاه‌تر باشد.
    مثلاً ۳۱ام + ۱ ماه در مهر می‌شود ۳۰ مهر.
    """
    total = (year * 12 + (month - 1)) + count
    y, m = divmod(total, 12)
    m += 1
    return y, m, min(day, month_length(y, m))


def month_label(year: int, month: int) -> str:
    return f"{MONTH_NAMES_FA[month - 1]} {year}"


def month_range(year: int, month: int) -> tuple[date, date]:
    """بازهٔ میلادیِ یک ماه جلالی: [شروع، شروعِ ماه بعد)"""
    start = jdatetime.date(year, month, 1).togregorian()
    ny, nm, _ = add_months(year, month, 1, 1)
    return start, jdatetime.date(ny, nm, 1).togregorian()
