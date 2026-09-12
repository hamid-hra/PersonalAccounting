import datetime as dt

import pytest

from app.services.jalali import (
    add_months,
    month_length,
    month_range,
    parse_jalali,
    parse_jalali_date,
    to_jalali_str,
)


def test_parse_datetime():
    greg, canonical = parse_jalali("1405/06/10 18:42:09")
    assert canonical == "1405/06/10 18:42:09"
    assert to_jalali_str(greg) == "1405/06/10"


def test_parse_accepts_persian_digits():
    greg, canonical = parse_jalali("۱۴۰۴/۰۷/۰۶")
    assert canonical == "1404/07/06 00:00:00"
    assert parse_jalali_date("۱۴۰۴/۰۷/۰۶") == greg.date()


def test_month_lengths():
    assert month_length(1404, 1) == 31   # نیمهٔ اول سال
    assert month_length(1404, 8) == 30   # نیمهٔ دوم سال
    assert month_length(1403, 12) == 30  # اسفندِ سال کبیسه
    assert month_length(1404, 12) == 29


def test_add_months_clamps_to_short_month():
    """۳۱ شهریور + ۱ ماه باید ۳۰ مهر شود، نه اینکه به آبان سر برود."""
    assert add_months(1404, 6, 31, 1) == (1404, 7, 30)
    assert add_months(1404, 7, 6, 11) == (1405, 6, 6)
    assert add_months(1404, 12, 29, 1) == (1405, 1, 29)


def test_month_range_is_half_open():
    start, end = month_range(1405, 6)
    assert start == parse_jalali_date("1405/06/01")
    assert end == parse_jalali_date("1405/07/01")


def test_invalid_date_raises():
    with pytest.raises(ValueError):
        parse_jalali("not a date")
