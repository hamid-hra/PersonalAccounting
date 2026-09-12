"""
تست پذیرش روی صورتحساب واقعی بانک ملی (سامانهٔ بام).

فایل ملی جمع‌های سرصفحه ندارد، ولی ستون مانده‌اش بی‌نقص است — پس معیار
درستیِ پارس، پیوستگی کاملِ زنجیرهٔ مانده است.
"""

import pytest

from app.importers.melli import MelliImporter, iban_from_account, parse_details
from tests.conftest import SAMPLE_MELLI, SAMPLE_SAMAN

# صورتحساب واقعی داخل مخزن نیست (دادهٔ شخصی)؛ تست‌های وابسته به فایل skip می‌شوند
needs_sample = pytest.mark.skipif(
    not (SAMPLE_MELLI.exists() and SAMPLE_SAMAN.exists()),
    reason="فایل‌های نمونهٔ بانک در دسترس نیستند",
)

EXPECTED_ROWS = 78
EXPECTED_DEPOSIT = 14_346_295_240
EXPECTED_WITHDRAW = 14_345_921_690
EXPECTED_CLOSING = 373_550


@pytest.fixture(scope="module")
def parsed():
    return MelliImporter().parse(SAMPLE_MELLI)


@needs_sample
def test_sniff_recognizes_melli_and_rejects_saman():
    assert MelliImporter().sniff(SAMPLE_MELLI) is True
    # xlsx سامان نباید با آداپتور ملی اشتباه گرفته شود
    assert MelliImporter().sniff(SAMPLE_SAMAN) is False


@needs_sample
def test_header_metadata(parsed):
    m = parsed.meta
    assert m.owner_name
    assert m.account_number.isdigit()
    assert m.iban == iban_from_account(m.account_number)
    assert m.period_from_jalali == "1404/06/10"


@needs_sample
def test_row_count_and_sums(parsed):
    assert len(parsed.transactions) == EXPECTED_ROWS
    assert sum(t.deposit_rial for t in parsed.transactions) == EXPECTED_DEPOSIT
    assert sum(t.withdraw_rial for t in parsed.transactions) == EXPECTED_WITHDRAW


@needs_sample
def test_balance_chain_is_perfect(parsed):
    """ستون ماندهٔ بانک ملی باید بدون هیچ پرشی پیوسته باشد."""
    report = MelliImporter().validate(parsed)
    checks = {c["name"]: c for c in report["checks"]}
    assert checks["پرش موضعی در ستون مانده"]["actual"] == 0
    assert checks["ماندهٔ پایانی سطر آخر"]["actual"] == EXPECTED_CLOSING
    assert report["ok"] is True


@needs_sample
def test_self_declared_transfers_detected(parsed):
    """
    بانک ملی خودش «انتقال پول بين حساب هاي خود» را علامت می‌زند —
    این حدس نیست و نباید از دست برود.
    """
    assert sum(1 for t in parsed.transactions if t.is_self_declared) == 21


@needs_sample
def test_user_notes_are_imported(parsed):
    """یادداشت‌هایی که کاربر در اپ بانک نوشته، ارزشمندترین دادهٔ فایل‌اند."""
    notes = [t.user_note for t in parsed.transactions if t.user_note]
    assert len(notes) == 14
    assert any("حقوق" in n for n in notes)
    assert any("وام" in n for n in notes)


@needs_sample
def test_loan_disbursement_present(parsed):
    loans = [t for t in parsed.transactions if t.bank_tx_type == "تسهیلات مالی"]
    assert len(loans) == 1
    assert loans[0].deposit_rial == 3_000_000_000


@needs_sample
def test_dedup_hash_unique(parsed):
    assert len({t.dedup_hash() for t in parsed.transactions}) == EXPECTED_ROWS


@needs_sample
def test_structured_details_beat_free_text(parsed):
    """ستون توضیحاتِ ملی نام و شبا را آماده می‌دهد؛ نباید حدس زده شود."""
    with_iban = [t for t in parsed.transactions if (t.details or {}).get("counterparty_iban")]
    assert len(with_iban) >= 30
    assert all(d["counterparty_iban"].startswith("IR") for d in (t.details for t in with_iban))


# ---------------------------------------------------------------- واحدها
def test_parse_details_key_values():
    text = (
        "شماره حساب طرف مقابل : 0200000000002،  نام کامل طرف مقابل : على رضايى،"
        "  نوع : انتقال پول بين حساب هاي خود"
    )
    d = parse_details(text)
    assert d["counterparty_account"] == "0200000000002"
    assert d["counterparty_name"] == "علی رضایی"
    assert "انتقال پول" in d["kind"]


def test_parse_details_with_iban_and_fee():
    text = (
        "   کارمزد : 5000،  بانک طرف مقابل : بانک سامان،  نام کامل طرف مقابل : "
        "على رضايي، شماره شبای طرف مقابل : IR500560610000000000000001"
    )
    d = parse_details(text)
    assert d["fee"] == "5000"
    assert d["counterparty_bank"] == "بانک سامان"
    assert d["counterparty_iban"] == "IR500560610000000000000001"


def test_parse_details_empty():
    assert parse_details("") == {}
    assert parse_details("بدون جداکننده") == {}


def test_iban_check_digits():
    """
    شبا از شمارهٔ حساب ساخته می‌شود تا تطبیق بین‌بانکی کار کند.
    رقم کنترل با پیاده‌سازی مرجع mod-97 حساب شده است.
    """
    assert iban_from_account("0100000000001") == "IR380170000000100000000001"
    assert iban_from_account("0200000000002") == "IR700170000000200000000002"
    assert iban_from_account("") is None
