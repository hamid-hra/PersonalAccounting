"""تست منطق دسته‌بندی — به‌ویژه تشخیص انتقال بین حساب‌های خودِ کاربر."""

from datetime import date, datetime

import pytest

from app.enums import CategorizedBy
from app.models import Category, Contact, ContactIdentifier, OwnerAlias, Rule, Transaction
from app.services.categorize import Categorizer
from app.services.normalize import fold, fold_name


def make_tx(**kwargs) -> Transaction:
    base = dict(
        account_id=1,
        occurred_at=datetime(2026, 1, 1),
        occurred_date=date(2026, 1, 1),
        jalali_datetime="1404/10/11 10:00:00",
        jalali_year=1404,
        jalali_month=10,
        jalali_day=11,
        amount_rial=-1_000_000,
        direction="out",
        description_raw="",
        description_norm="",
        dedup_hash="x",
        categorized_by=CategorizedBy.NONE,
        needs_review=True,
    )
    base.update(kwargs)
    return Transaction(**base)


@pytest.fixture
def seeded(db):
    uncategorized = Category(slug="uncategorized", name_fa="بدون دسته", kind="expense")
    self_cat = Category(slug="self_transfer", name_fa="انتقال به خودم", kind="transfer")
    groceries = Category(slug="groceries", name_fa="خواربار", kind="expense")
    fee = Category(slug="bank_fee", name_fa="کارمزد بانکی", kind="fee")
    db.add_all([uncategorized, self_cat, groceries, fee])
    db.flush()

    db.add(
        OwnerAlias(kind="name", value="علی رضایی", value_norm=fold_name("علی رضایی"))
    )
    db.add(Rule(name="کارمزد", priority=10, is_system=True, is_active=True,
                match_bank_tx_type="کارمزد", set_category_id=fee.id, set_needs_review=False))
    db.flush()
    return {"uncategorized": uncategorized, "self": self_cat, "groceries": groceries, "fee": fee}


def test_self_transfer_detected_by_name(db, seeded):
    """۴۲٪ خروجی حساب واقعی همین بود؛ اگر شناسایی نشود همهٔ آمار غلط می‌شود."""
    tx = make_tx(counterparty_name="علی رضایی", counterparty_name_norm=fold_name("علی رضایی"))
    Categorizer(db).apply(tx)
    assert tx.is_self_transfer is True
    assert tx.category_id == seeded["self"].id
    assert tx.needs_review is False


def test_self_transfer_matches_across_encodings(db, seeded):
    tx = make_tx(counterparty_name="على رضايى", counterparty_name_norm=fold_name("على رضايى"))
    Categorizer(db).apply(tx)
    assert tx.is_self_transfer is True


def test_other_person_is_not_self_transfer(db, seeded):
    tx = make_tx(counterparty_name="سعیده قادری", counterparty_name_norm=fold_name("سعیده قادری"))
    Categorizer(db).apply(tx)
    assert tx.is_self_transfer is False


def test_loan_payment_mentioning_owner_is_still_an_expense(db, seeded):
    """
    شرح قسط وام نام صاحب حساب را دارد («متعلق به …») ولی چون طرف‌حساب
    استخراج نمی‌شود، نباید انتقال داخلی شمرده شود.
    """
    tx = make_tx(
        bank_tx_type="اقساط تسهیلات",
        description_raw="برداشت بابت پرداخت قسط تسهیلات شماره: LN_0000123456 - متعلق به علی رضایی",
        loan_ref="LN_0000123456",
    )
    Categorizer(db).apply(tx)
    assert tx.is_self_transfer is False


def test_contact_identifier_wins_over_rules(db, seeded):
    contact = Contact(name_fa="سوپرمارکت", name_norm="سوپرمارکت", category_id=seeded["groceries"].id)
    db.add(contact)
    db.flush()
    db.add(ContactIdentifier(contact_id=contact.id, kind="pos_terminal", value="07329842"))
    db.flush()

    tx = make_tx(terminal_id="07329842", terminal_kind="pos_terminal", bank_tx_type="خرید از فروشگاه")
    Categorizer(db).apply(tx)
    assert tx.contact_id == contact.id
    assert tx.category_id == seeded["groceries"].id
    assert tx.categorized_by == CategorizedBy.CONTACT
    assert tx.needs_review is False


def test_system_rule_by_bank_type(db, seeded):
    tx = make_tx(bank_tx_type="کارمزد")
    Categorizer(db).apply(tx)
    assert tx.category_id == seeded["fee"].id
    assert tx.needs_review is False


def test_unknown_falls_back_to_review_queue(db, seeded):
    tx = make_tx(bank_tx_type="خرید از فروشگاه", terminal_id="99999999", terminal_kind="pos_terminal")
    Categorizer(db).apply(tx)
    assert tx.category_id == seeded["uncategorized"].id
    assert tx.needs_review is True


def test_manual_label_is_never_overwritten(db, seeded):
    tx = make_tx(
        bank_tx_type="کارمزد",
        category_id=seeded["groceries"].id,
        categorized_by=CategorizedBy.MANUAL,
    )
    Categorizer(db).apply(tx)
    assert tx.category_id == seeded["groceries"].id
    # مگر آنکه صراحتاً force بخواهیم
    Categorizer(db).apply(tx, force=True)
    assert tx.category_id == seeded["fee"].id


def test_contact_income_category_differs_from_expense(db, seeded):
    """
    «اگر از این مخاطب پول آمد، حقوقم است» — ولی وقتی به او پول می‌دهم
    باید دستهٔ دیگری بخورد. یک دسته برای هر دو جهت کافی نیست.
    """
    salary = Category(slug="salary", name_fa="حقوق", kind="income")
    db.add(salary)
    db.flush()

    employer = Contact(
        name_fa="شرکت نمونه",
        name_norm=fold_name("شرکت نمونه"),
        kind="business",
        category_id=seeded["groceries"].id,   # وقتی پول می‌دهم
        income_category_id=salary.id,          # وقتی پول می‌گیرم
    )
    db.add(employer)
    db.flush()
    db.add(ContactIdentifier(contact_id=employer.id, kind="iban", value="IR530570000000000000000123"))
    db.flush()

    incoming = make_tx(amount_rial=102_500_000, direction="in",
                       counterparty_iban="IR530570000000000000000123")
    outgoing = make_tx(amount_rial=-5_000_000, direction="out",
                       counterparty_iban="IR530570000000000000000123")
    cat = Categorizer(db)
    cat.apply(incoming)
    cat.apply(outgoing)

    assert incoming.category_id == salary.id
    assert outgoing.category_id == seeded["groceries"].id


def test_contact_matched_by_name_when_no_identifier(db, seeded):
    """اگر تراکنش شناسه نداشت، نام (بی‌اعتنا به ترتیب) کافی است."""
    person = Contact(name_fa="سعیده قادری", name_norm=fold_name("سعیده قادری"),
                     category_id=seeded["groceries"].id)
    db.add(person)
    db.flush()

    tx = make_tx(counterparty_name="قادری سعیده")
    Categorizer(db).apply(tx)
    assert tx.contact_id == person.id
