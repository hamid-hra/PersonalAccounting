"""
تست کشف پیوند بین تراکنش‌ها.

سه چیزی که اگر خراب شود، آمار بی‌سروصدا غلط می‌شود: انتقال بین حساب‌های
خودم، حوالهٔ برگشتی، و کارمزدِ سطرِ جدا.
"""

from datetime import datetime, timedelta

import pytest

from app.models import Account, Transaction
from app.services.links import apply_links, detect_links

SAMAN_IBAN = "IR500560610000000000000001"
MELLI_IBAN = "IR380170000000100000000001"


def make_tx(account_id: int, *, amount: int, when: datetime, **kwargs) -> Transaction:
    base = dict(
        account_id=account_id,
        occurred_at=when,
        occurred_date=when.date(),
        jalali_datetime="1405/02/14 10:00:00",
        jalali_year=1405,
        jalali_month=2,
        jalali_day=14,
        amount_rial=amount,
        direction="in" if amount > 0 else "out",
        description_raw="",
        description_norm="",
        dedup_hash=f"h{account_id}-{amount}-{when.timestamp()}",
    )
    base.update(kwargs)
    return Transaction(**base)


@pytest.fixture
def two_accounts(db):
    saman = Account(bank="saman", title="سامان", iban=SAMAN_IBAN, account_number="610000000000000001")
    melli = Account(bank="melli", title="ملی", iban=MELLI_IBAN, account_number="0100000000001")
    db.add_all([saman, melli])
    db.flush()
    return saman, melli


def test_cross_account_transfer_is_paired(db, two_accounts):
    """
    الگوی واقعی: انتقال پل از ملی به سامان، ۴ ثانیه فاصله، مبلغ یکسان.
    بدون جفت‌شدن، یک جابه‌جایی هم هزینه می‌شود هم درآمد.
    """
    saman, melli = two_accounts
    now = datetime(2026, 5, 6, 9, 56, 53)
    out = make_tx(melli.id, amount=-4_000_000, when=now, counterparty_iban=SAMAN_IBAN)
    inn = make_tx(saman.id, amount=4_000_000, when=now + timedelta(seconds=4),
                  counterparty_iban=MELLI_IBAN)
    db.add_all([out, inn])
    db.flush()

    created = detect_links(db)
    assert created["cross_account"] == 1
    assert out.is_self_transfer is True
    assert inn.is_self_transfer is True


def test_cross_account_needs_matching_identity(db, two_accounts):
    """مبلغ و زمانِ یکسان به‌تنهایی کافی نیست — باید شبا هم بخواند."""
    saman, melli = two_accounts
    now = datetime(2026, 5, 6, 9, 0, 0)
    db.add_all([
        make_tx(melli.id, amount=-4_000_000, when=now, counterparty_iban="IR999999999999999999999999"),
        make_tx(saman.id, amount=4_000_000, when=now + timedelta(seconds=4)),
    ])
    db.flush()
    assert detect_links(db)["cross_account"] == 0


def test_reversal_detected_and_excluded(db, two_accounts):
    """حوالهٔ ساتنای ناموفق که برمی‌گردد — نه هزینه است نه درآمد."""
    saman, _ = two_accounts
    now = datetime(2026, 5, 4, 10, 1, 3)
    out = make_tx(saman.id, amount=-1_000_000_000, when=now, bank_tx_type="حواله ساتنا")
    back = make_tx(saman.id, amount=1_000_000_000, when=now + timedelta(seconds=44),
                   bank_tx_type="حواله برگشتی ساتنا")
    db.add_all([out, back])
    db.flush()

    created = detect_links(db)
    assert created["reversal"] == 1
    assert out.is_reversed is True
    assert back.is_reversed is True


def test_distant_small_amounts_are_low_confidence(db, two_accounts):
    """
    دو مبلغ گردِ کوچک با فاصلهٔ چند روز، شاهدِ ارتباط نیستند.
    پیوند ساخته می‌شود ولی خودکار اعمال نمی‌شود تا کاربر تأیید کند.
    """
    from app.models import TxLink
    from sqlalchemy import select

    saman, _ = two_accounts
    now = datetime(2026, 5, 1, 8, 0, 0)
    out = make_tx(saman.id, amount=-5_000, when=now, bank_tx_type="کارمزد")
    back = make_tx(saman.id, amount=5_000, when=now + timedelta(hours=100),
                   bank_tx_type="اصلاح سند")
    db.add_all([out, back])
    db.flush()

    detect_links(db)
    link = db.scalar(select(TxLink).where(TxLink.kind == "reversal"))
    assert link is not None
    assert link.confidence < 0.7
    assert out.is_reversed is False  # اعمال نشده


def test_confirming_low_confidence_link_applies_it(db, two_accounts):
    from app.models import TxLink
    from sqlalchemy import select

    saman, _ = two_accounts
    now = datetime(2026, 5, 1, 8, 0, 0)
    out = make_tx(saman.id, amount=-5_000, when=now, bank_tx_type="کارمزد")
    back = make_tx(saman.id, amount=5_000, when=now + timedelta(hours=100),
                   bank_tx_type="اصلاح سند")
    db.add_all([out, back])
    db.flush()
    detect_links(db)

    link = db.scalar(select(TxLink).where(TxLink.kind == "reversal"))
    link.is_confirmed = True
    db.commit()
    apply_links(db)
    assert out.is_reversed is True


def test_fee_linked_by_shared_reference(db, two_accounts):
    """کارمزد سطر جدا دارد ولی شمارهٔ پیگیری‌اش با تراکنش اصلی یکی است."""
    saman, _ = two_accounts
    now = datetime(2026, 5, 6, 9, 56, 53)
    parent = make_tx(saman.id, amount=-4_000_000, when=now,
                     bank_tx_type="حواله پل", doc_number="BCG11264")
    fee = make_tx(saman.id, amount=-5_000, when=now,
                  bank_tx_type="کارمزد حواله پل", doc_number="Z_G11264")
    db.add_all([parent, fee])
    db.flush()
    assert detect_links(db)["fee"] == 1


def test_detect_is_idempotent(db, two_accounts):
    saman, melli = two_accounts
    now = datetime(2026, 5, 6, 9, 56, 53)
    db.add_all([
        make_tx(melli.id, amount=-4_000_000, when=now, counterparty_iban=SAMAN_IBAN),
        make_tx(saman.id, amount=4_000_000, when=now + timedelta(seconds=4),
                counterparty_iban=MELLI_IBAN),
    ])
    db.flush()
    first = detect_links(db)
    second = detect_links(db)
    assert first["cross_account"] == 1
    assert second["cross_account"] == 0  # دوباره ساخته نشد
