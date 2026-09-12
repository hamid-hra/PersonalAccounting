"""
تست تعریف درآمد.

قبلاً هر واریزی درآمد شمرده می‌شد. روی دادهٔ واقعی این یعنی یک وام ۳۰۰
میلیون تومانی و پس‌گرفتن قرض هم «درآمد» بود. حالا فقط چیزی درآمد است که
کاربر تأییدش کرده باشد.
"""

from datetime import date, datetime

import pytest

from app.models import Category, Contact, ContactIdentifier, Transaction
from app.services.analytics import summary
from app.services.categorize import Categorizer
from app.services.normalize import fold_name


def make_tx(**kwargs) -> Transaction:
    base = dict(
        account_id=kwargs.pop("account_id", 1),
        occurred_at=datetime(2026, 5, 1, 10, 0),
        occurred_date=date(2026, 5, 1),
        jalali_datetime="1405/02/11 10:00:00",
        jalali_year=1405,
        jalali_month=2,
        jalali_day=11,
        amount_rial=1_000_000,
        direction="in",
        description_raw="",
        description_norm="",
        dedup_hash=f"h{id(kwargs)}{kwargs.get('amount_rial', 0)}",
    )
    base.update(kwargs)
    return Transaction(**base)


@pytest.fixture
def account(db):
    from app.models import Account

    acc = Account(bank="saman", title="آزمایش")
    db.add(acc)
    db.flush()
    return acc


@pytest.fixture
def cats(db):
    """حداقل دسته‌هایی که موتور دسته‌بندی برای کار کردن لازم دارد."""
    rows = {
        "uncategorized": Category(slug="uncategorized", name_fa="بدون دسته", kind="expense"),
        "self_transfer": Category(slug="self_transfer", name_fa="انتقال به خودم", kind="transfer"),
        "groceries": Category(slug="groceries", name_fa="خواربار", kind="expense"),
    }
    db.add_all(rows.values())
    db.flush()
    return rows


def test_unconfirmed_deposit_is_not_income(db, account):
    """واریزیِ بلاتکلیف نباید در درآمد شمرده شود."""
    db.add(make_tx(account_id=account.id, amount_rial=5_000_000, is_income=None))
    db.commit()
    s = summary(db, 1405, 2)
    assert s["month_income_rial"] == 0
    assert s["pending_income_count"] == 1
    assert s["pending_income_rial"] == 5_000_000


def test_confirmed_deposit_counts(db, account):
    db.add(make_tx(account_id=account.id, amount_rial=5_000_000, is_income=True))
    db.commit()
    s = summary(db, 1405, 2)
    assert s["month_income_rial"] == 5_000_000
    assert s["pending_income_count"] == 0


def test_rejected_deposit_never_counts(db, account):
    """وامی که گرفته‌ای درآمد نیست، هرچند پول وارد حساب شده."""
    db.add(make_tx(account_id=account.id, amount_rial=3_000_000_000, is_income=False))
    db.commit()
    s = summary(db, 1405, 2)
    assert s["month_income_rial"] == 0
    assert s["pending_income_count"] == 0


def test_expenses_are_unaffected(db, account):
    """تغییر تعریف درآمد نباید هزینه را دست بزند."""
    db.add(make_tx(account_id=account.id, amount_rial=-2_000_000, direction="out"))
    db.commit()
    assert summary(db, 1405, 2)["month_expense_rial"] == 2_000_000


def test_self_transfer_is_marked_not_income(db, account, cats):
    """پول خودم که جابه‌جا شده، نه درآمد است نه منتظر تصمیم."""
    from app.models import OwnerAlias

    db.add(OwnerAlias(kind="name", value="علی رضایی", value_norm=fold_name("علی رضایی")))
    db.flush()
    tx = make_tx(account_id=account.id, counterparty_name="رضایی علی")
    Categorizer(db).apply(tx)
    assert tx.is_self_transfer is True
    assert tx.is_income is False


def test_known_employer_auto_confirms_income(db, account, cats):
    """
    وقتی برای یک مخاطب «دستهٔ دریافت» تعیین کرده‌ای، یعنی قبلاً گفته‌ای
    پولی که از او می‌آید درآمد است — واریزی‌های بعدی‌اش نباید دوباره بپرسند.
    """
    salary = Category(slug="salary_test", name_fa="حقوق", kind="income")
    db.add(salary)
    db.flush()
    employer = Contact(
        name_fa="شرکت نمونه",
        name_norm=fold_name("شرکت نمونه"),
        income_category_id=salary.id,
    )
    db.add(employer)
    db.flush()
    db.add(ContactIdentifier(contact_id=employer.id, kind="iban", value="IR78"))
    db.flush()

    tx = make_tx(account_id=account.id, counterparty_iban="IR78")
    Categorizer(db).apply(tx)
    assert tx.is_income is True
    assert tx.category_id == salary.id


def test_contact_without_income_category_stays_pending(db, account, cats):
    """مخاطبی که فقط دستهٔ پرداخت دارد، واریزی‌اش خودکار درآمد نمی‌شود."""
    person = Contact(
        name_fa="آرش شکری",
        name_norm=fold_name("آرش شکری"),
        category_id=cats["groceries"].id,
    )
    db.add(person)
    db.flush()
    db.add(ContactIdentifier(contact_id=person.id, kind="card", value="6037"))
    db.flush()

    tx = make_tx(account_id=account.id, counterparty_card="6037")
    Categorizer(db).apply(tx)
    assert tx.is_income is None
