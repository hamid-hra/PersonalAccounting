"""
تست سرویس قیمت.

مهم‌ترین چیزی که اینجا محافظت می‌شود: **واحد قیمت**. سرویس تومان می‌دهد و
برنامه ریال نگه می‌دارد؛ اگر این تبدیل بشکند، همهٔ اعداد ده برابر غلط
می‌شوند بدون آنکه هیچ خطایی داده شود.
"""

from datetime import date

import pytest

from app.services.market.brsapi import BrsApiProvider, to_rial
from app.services.market.service import all_providers, provider


def test_toman_is_converted_to_rial():
    # پاسخ واقعی سرویس: طلای ۱۸ عیار ۶٬۲۱۴٬۷۰۰ تومان
    assert to_rial(6_214_700, "تومان") == 62_147_000
    assert to_rial(81_650, "تومان") == 816_500


def test_rial_is_left_alone():
    assert to_rial(62_147_000, "ریال") == 62_147_000


def test_missing_unit_defaults_to_toman():
    """سرویس همیشه تومان می‌دهد؛ نبودِ واحد نباید عدد را خراب کند."""
    assert to_rial(1000, None) == 10_000
    assert to_rial(1000, "") == 10_000


def test_unparsable_price_is_none():
    for bad in (None, "", "-", "چیزی"):
        assert to_rial(bad, "تومان") is None


def test_items_are_exactly_what_user_asked_for():
    """سکه و طلای آب‌شده و درهم نباید برگردند."""
    codes = {i.code for i in BrsApiProvider().items}
    assert codes == {"IR_GOLD_18K", "IR_GOLD_24K", "USD", "EUR"}


def test_provider_default_is_brsapi(db):
    """بدون هیچ تنظیمی، سرویس رایگان پیش‌فرض است."""
    assert provider(db).name == "brsapi"
    assert {p["name"] for p in all_providers()} == {"brsapi", "navasan"}


def test_provider_reads_key_from_app_settings(db, monkeypatch):
    """
    کلید از تنظیمات برنامه می‌آید نه از محیط — تا کاربر بتواند از داخل
    خود برنامه عوضش کند بدون دست‌زدن به فایل و بالا و پایین کردن سرویس.

    مقدار محیطی عمداً خالی می‌شود: تست واحد نباید به محیطِ ماشینی که
    روی آن اجرا می‌شود وابسته باشد.
    """
    from app.config import settings
    from app.services import appsettings

    monkeypatch.setattr(settings, "brsapi_key", "")
    assert provider(db).is_configured() is False
    appsettings.set(db, appsettings.BRSAPI_KEY, "test-key-123")
    prov = provider(db)
    assert prov.is_configured() is True
    assert prov.api_key == "test-key-123"


def test_switching_provider_from_settings(db):
    from app.services import appsettings

    appsettings.set(db, appsettings.MARKET_PROVIDER, "navasan")
    assert provider(db).name == "navasan"


def test_quota_is_daily_and_generous():
    """
    دلیل عوض‌کردن سرویس همین بود: ۱۵۰۰ در روز به‌جای ۱۲۰ در ماه.
    """
    spec = BrsApiProvider().quota()
    assert spec.window == "day"
    assert spec.limit >= 1000


def test_unconfigured_provider_refuses_before_calling(monkeypatch):
    """بدون کلید نباید اصلاً درخواستی زده شود."""
    from app.config import settings
    from app.services.market.base import MarketUnavailable

    monkeypatch.setattr(settings, "brsapi_key", "")
    with pytest.raises(MarketUnavailable):
        BrsApiProvider().fetch_latest(["USD"])


def test_latest_parses_real_response_shape(monkeypatch):
    """شکل پاسخ واقعی سرویس — بخش‌های gold و currency کنار هم."""
    payload = {
        "gold": [
            {"symbol": "IR_GOLD_18K", "price": 6_214_700, "change_percent": -1.53,
             "change_value": -95_100, "unit": "تومان", "date": "1404/02/28"},
            {"symbol": "IR_COIN_EMAMI", "price": 90_000_000, "unit": "تومان"},
        ],
        "currency": [
            {"symbol": "USD", "price": 81_650, "change_percent": -0.91,
             "unit": "تومان", "date": "1404/02/28"},
        ],
        "cryptocurrency": [{"symbol": "BTC", "price": 1, "unit": "تومان"}],
    }
    prov = BrsApiProvider()
    monkeypatch.setattr(prov, "_get", lambda params: payload)

    quotes = {q.code: q for q in prov.fetch_latest(["IR_GOLD_18K", "USD"])}
    assert set(quotes) == {"IR_GOLD_18K", "USD"}   # سکه خواسته نشده بود
    assert quotes["IR_GOLD_18K"].price_rial == 62_147_000
    assert quotes["IR_GOLD_18K"].change_percent == -1.53
    assert quotes["USD"].as_of == date(2025, 5, 18)


def test_history_parses_range(monkeypatch):
    prov = BrsApiProvider()
    monkeypatch.setattr(
        prov,
        "_get",
        lambda params: [
            {"date": "1404/01/01", "price": 80_000, "unit": "تومان"},
            {"date": "1404/01/02", "price": 81_000, "unit": "تومان"},
        ],
    )
    points = prov.fetch_history("USD", date(2025, 3, 21), date(2025, 3, 23))
    assert [p.close_rial for p in points] == [800_000, 810_000]
