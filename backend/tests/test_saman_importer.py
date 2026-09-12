"""
تست پذیرش روی صورتحساب واقعی.

اعداد انتظاری از سرصفحهٔ خودِ فایل می‌آیند — اگر پارس اشتباه شود، جمع‌ها
نمی‌خوانند. این قوی‌ترین تضمینی است که بدون داده‌ی ساختگی می‌شود داشت.
"""

import pytest

from app.importers.saman import SamanImporter
from tests.conftest import SAMPLE

# صورتحساب واقعی داخل مخزن نیست (دادهٔ شخصی)؛ بدون آن این تست‌ها رد می‌شوند
pytestmark = pytest.mark.skipif(not SAMPLE.exists(), reason="sample_saman.xlsx در دسترس نیست")

EXPECTED_ROWS = 1215
EXPECTED_DEPOSIT = 4_479_113_120
EXPECTED_WITHDRAW = 4_478_456_028
EXPECTED_CLOSING = 5_118_184
EXPECTED_OPENING = 4_461_092


@pytest.fixture(scope="module")
def parsed():
    return SamanImporter().parse(SAMPLE)


def test_sniff_recognizes_saman_file():
    assert SamanImporter().sniff(SAMPLE) is True


def test_header_metadata(parsed):
    m = parsed.meta
    assert m.owner_name
    assert m.iban.startswith("IR") and len(m.iban) == 26
    assert m.account_number and m.iban.endswith(m.account_number)
    assert m.opened_at_jalali == "1401/07/22"
    # دورهٔ صورتحساب در فایل به شکل روز/ماه/سال نوشته شده
    assert m.period_from_jalali == "1404/06/10"
    assert m.period_to_jalali == "1405/06/10"
    assert m.opening_balance_rial == EXPECTED_OPENING
    assert m.closing_balance_rial == EXPECTED_CLOSING


def test_row_count(parsed):
    assert len(parsed.transactions) == EXPECTED_ROWS


def test_sums_match_file_header(parsed):
    assert sum(t.deposit_rial for t in parsed.transactions) == EXPECTED_DEPOSIT
    assert sum(t.withdraw_rial for t in parsed.transactions) == EXPECTED_WITHDRAW


def test_opening_plus_net_equals_closing(parsed):
    net = EXPECTED_DEPOSIT - EXPECTED_WITHDRAW
    assert EXPECTED_OPENING + net == EXPECTED_CLOSING


def test_dedup_hash_is_unique_across_every_row(parsed):
    """
    کلید تشخیص تکرار باید روی هر ۱۲۱۵ سطر یکتا باشد، وگرنه ورودِ دوبارهٔ
    همان فایل تراکنش‌های واقعی را دور می‌ریزد.
    """
    hashes = {t.dedup_hash() for t in parsed.transactions}
    assert len(hashes) == EXPECTED_ROWS


def test_doc_number_is_not_unique_enough_for_dedup(parsed):
    """چرا «شماره سند» کلید مناسبی نیست: بین سطر کارمزد و سطر اصلی مشترک است."""
    docs = {t.doc_number for t in parsed.transactions if t.doc_number}
    assert len(docs) < EXPECTED_ROWS


def test_validation_passes(parsed):
    report = SamanImporter().validate(parsed)
    assert report["ok"] is True
    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert statuses["جمع کل واریز"] == "ok"
    assert statuses["جمع کل برداشت"] == "ok"
    # پرش‌های موضعی مانده در فایل بانک هست و نباید ورود را رد کند
    assert statuses["پرش موضعی در ستون مانده"] in {"ok", "warn"}


def test_amounts_are_integers_not_floats(parsed):
    assert all(isinstance(t.withdraw_rial, int) for t in parsed.transactions)
    assert all(isinstance(t.deposit_rial, int) for t in parsed.transactions)


def test_loan_installments_detected(parsed):
    from app.services.extract import extract

    from collections import Counter

    refs = Counter(
        extract(t.description_raw).loan_ref
        for t in parsed.transactions
        if extract(t.description_raw).loan_ref
    )
    # یک وام با قسط‌های ماهانه باید چند بار با همان شماره دیده شود
    assert refs and max(refs.values()) >= 6
