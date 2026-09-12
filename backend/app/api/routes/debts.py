"""
دفتر قرض — پولی که به کسی دادم یا از کسی گرفتم.

برخلاف وام بانکی، قرض جدول اقساط ندارد. هر رویداد (اصل مبلغ یا بازپرداخت)
وقتی رخ داد ثبت می‌شود و معمولاً به یک تراکنش بانکی وصل است، تا بشود گفت
«این پول قرض بود، نه خرج».
"""

from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.enums import DEBT_DIRECTION_LABELS_FA, DebtDirection, DebtEntryKind, DebtStatus
from app.models import Contact, Debt, DebtEntry, Transaction
from app.services.jalali import parse_jalali_date, to_jalali_str
from app.services.normalize import fold_name, fold_name_key

router = APIRouter()


def serialize_entry(e: DebtEntry) -> dict:
    return {
        "id": e.id,
        "kind": e.kind,
        "kind_label": "اصل مبلغ" if e.kind == DebtEntryKind.PRINCIPAL else "بازپرداخت",
        "amount_rial": e.amount_rial,
        "entry_jalali": e.entry_jalali,
        "transaction_id": e.transaction_id,
        "note": e.note,
    }


def serialize(d: Debt, *, detail: bool = False) -> dict:
    data = {
        "id": d.id,
        "contact_id": d.contact_id,
        "person_name": d.person_name,
        "direction": d.direction,
        "direction_label": DEBT_DIRECTION_LABELS_FA.get(DebtDirection(d.direction), d.direction),
        "principal_rial": d.principal_rial,
        "repaid_rial": d.repaid_rial,
        "outstanding_rial": d.outstanding_rial,
        "progress": (d.repaid_rial / d.principal_rial) if d.principal_rial else 0,
        "account_id": d.account_id,
        "account_title": d.account.title if d.account else None,
        "is_cash": d.is_cash,
        "opened_jalali": d.opened_jalali,
        "due_jalali": d.due_jalali,
        "status": d.status,
        "note": d.note,
    }
    if detail:
        data["entries"] = [serialize_entry(e) for e in d.entries]
    return data


def _refresh_status(debt: Debt) -> None:
    debt.status = DebtStatus.SETTLED if debt.is_settled else DebtStatus.OPEN


@router.get("")
def list_debts(db: DB, user: Auth, status_filter: str | None = None) -> list[dict]:
    stmt = select(Debt).order_by(Debt.opened_date.desc())
    if status_filter:
        stmt = stmt.where(Debt.status == status_filter)
    return [serialize(d) for d in db.scalars(stmt)]


@router.get("/summary")
def summary(db: DB, user: Auth) -> dict:
    """چقدر طلبکارم، چقدر بدهکارم."""
    debts = list(db.scalars(select(Debt).where(Debt.status == DebtStatus.OPEN)))
    lent = [d for d in debts if d.direction == DebtDirection.I_LENT]
    borrowed = [d for d in debts if d.direction == DebtDirection.I_BORROWED]
    return {
        "i_am_owed_rial": sum(d.outstanding_rial for d in lent),
        "i_owe_rial": sum(d.outstanding_rial for d in borrowed),
        "lent_count": len(lent),
        "borrowed_count": len(borrowed),
        "net_rial": sum(d.outstanding_rial for d in lent)
        - sum(d.outstanding_rial for d in borrowed),
    }


class DebtIn(BaseModel):
    person_name: str
    direction: str
    principal_rial: int
    opened_jalali: str
    contact_id: int | None = None
    account_id: int | None = None
    is_cash: bool = False
    due_jalali: str | None = None
    note: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_debt(payload: DebtIn, db: DB, user: Auth) -> dict:
    if payload.direction not in {d.value for d in DebtDirection}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "جهت قرض معتبر نیست.")
    if payload.principal_rial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ باید مثبت باشد.")
    try:
        opened = parse_jalali_date(payload.opened_jalali)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    debt = Debt(
        person_name=payload.person_name.strip(),
        direction=payload.direction,
        principal_rial=payload.principal_rial,
        opened_jalali=payload.opened_jalali,
        opened_date=opened,
        due_jalali=payload.due_jalali,
        contact_id=payload.contact_id,
        account_id=None if payload.is_cash else payload.account_id,
        is_cash=payload.is_cash,
        note=payload.note,
    )
    db.add(debt)
    db.commit()
    return serialize(debt, detail=True)


@router.get("/{debt_id}")
def get_debt(debt_id: int, db: DB, user: Auth) -> dict:
    debt = db.get(Debt, debt_id)
    if debt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرض پیدا نشد.")
    return serialize(debt, detail=True)


@router.delete("/{debt_id}")
def delete_debt(debt_id: int, db: DB, user: Auth) -> dict:
    debt = db.get(Debt, debt_id)
    if debt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرض پیدا نشد.")
    db.delete(debt)
    db.commit()
    return {"ok": True}


class EntryIn(BaseModel):
    amount_rial: int
    entry_jalali: str | None = None
    kind: str = DebtEntryKind.REPAYMENT
    transaction_id: int | None = None
    note: str | None = None


@router.post("/{debt_id}/entries", status_code=status.HTTP_201_CREATED)
def add_entry(debt_id: int, payload: EntryIn, db: DB, user: Auth) -> dict:
    debt = db.get(Debt, debt_id)
    if debt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرض پیدا نشد.")
    if payload.amount_rial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ باید مثبت باشد.")

    entry_jalali = payload.entry_jalali or to_jalali_str(date.today())
    try:
        entry_date = parse_jalali_date(entry_jalali)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.add(
        DebtEntry(
            debt_id=debt.id,
            kind=payload.kind,
            amount_rial=payload.amount_rial,
            entry_jalali=entry_jalali,
            entry_date=entry_date,
            transaction_id=payload.transaction_id,
            note=payload.note,
        )
    )
    db.flush()
    db.refresh(debt)
    _refresh_status(debt)
    db.commit()
    return serialize(debt, detail=True)


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, db: DB, user: Auth) -> dict:
    entry = db.get(DebtEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رکورد پیدا نشد.")
    debt = entry.debt
    db.delete(entry)
    db.flush()
    db.refresh(debt)
    _refresh_status(debt)
    db.commit()
    return {"ok": True}


class FromTransactionIn(BaseModel):
    """«این تراکنش قرض بود» — مستقیم از صفحهٔ تراکنش‌ها."""

    transaction_id: int
    direction: str | None = None
    person_name: str | None = None
    debt_id: int | None = None
    note: str | None = None


@router.post("/from-transaction", status_code=status.HTTP_201_CREATED)
def from_transaction(payload: FromTransactionIn, db: DB, user: Auth) -> dict:
    """
    قرض تازه از روی تراکنش می‌سازد، یا اگر `debt_id` بدهی، همان تراکنش را
    به‌عنوان بازپرداختِ قرضِ موجود ثبت می‌کند.
    """
    tx = db.get(Transaction, payload.transaction_id)
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تراکنش پیدا نشد.")

    amount = abs(tx.amount_rial)
    jalali = tx.jalali_datetime.split(" ")[0]

    # حالت ۱: بازپرداخت روی قرض موجود
    if payload.debt_id is not None:
        debt = db.get(Debt, payload.debt_id)
        if debt is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "قرض پیدا نشد.")
        db.add(
            DebtEntry(
                debt_id=debt.id,
                kind=DebtEntryKind.REPAYMENT,
                amount_rial=amount,
                entry_jalali=jalali,
                entry_date=tx.occurred_date,
                transaction_id=tx.id,
                note=payload.note,
            )
        )
        db.flush()
        db.refresh(debt)
        _refresh_status(debt)
        db.commit()
        return serialize(debt, detail=True)

    # حالت ۲: قرض تازه. جهت از روی جهت پول حدس زده می‌شود:
    # پول از حساب رفت → قرض دادم؛ پول آمد → قرض گرفتم.
    direction = payload.direction or (
        DebtDirection.I_LENT if tx.amount_rial < 0 else DebtDirection.I_BORROWED
    )
    name = (payload.person_name or tx.counterparty_name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "این تراکنش نام طرف مقابل ندارد؛ نام را بنویس."
        )

    contact = db.scalar(select(Contact).where(Contact.name_norm == fold_name(name)))
    debt = Debt(
        person_name=name,
        direction=direction,
        principal_rial=amount,
        opened_jalali=jalali,
        opened_date=tx.occurred_date,
        contact_id=contact.id if contact else None,
        note=payload.note,
    )
    db.add(debt)
    db.flush()
    db.add(
        DebtEntry(
            debt_id=debt.id,
            kind=DebtEntryKind.PRINCIPAL,
            amount_rial=amount,
            entry_jalali=jalali,
            entry_date=tx.occurred_date,
            transaction_id=tx.id,
        )
    )
    db.commit()
    db.refresh(debt)
    return serialize(debt, detail=True)


@router.get("/{debt_id}/suggest-transactions")
def suggest_transactions(debt_id: int, db: DB, user: Auth, limit: int = 12) -> list[dict]:
    """
    تراکنش‌های محتملِ همین قرض.

    اگر حساب مبدأ را گفته باشی، همان حساب در پنجرهٔ ±۵ روزِ تاریخ قرض و با
    مبلغ نزدیک جست‌وجو می‌شود. وصل‌کردنشان جلوی دوباره‌شمردن قرض و خرج را
    می‌گیرد.
    """
    from datetime import timedelta

    debt = db.get(Debt, debt_id)
    if debt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرض پیدا نشد.")
    if debt.is_cash:
        return []

    used = {
        e.transaction_id for e in db.scalars(select(DebtEntry)) if e.transaction_id
    }
    # «قرض دادم» یعنی پول رفته، «قرض گرفتم» یعنی پول آمده
    outgoing = debt.direction == DebtDirection.I_LENT

    stmt = select(Transaction).where(
        Transaction.amount_rial < 0 if outgoing else Transaction.amount_rial > 0,
        Transaction.occurred_date >= debt.opened_date - timedelta(days=5),
        Transaction.occurred_date <= debt.opened_date + timedelta(days=5),
    )
    if debt.account_id:
        stmt = stmt.where(Transaction.account_id == debt.account_id)

    rows = [t for t in db.scalars(stmt.order_by(Transaction.occurred_at)) if t.id not in used]
    rows.sort(key=lambda t: abs(abs(t.amount_rial) - debt.principal_rial))
    return [
        {
            "id": t.id,
            "jalali_datetime": t.jalali_datetime,
            "amount_rial": t.amount_rial,
            "account_title": t.account.title if t.account else None,
            "description": t.description_raw[:120],
            "exact_match": abs(t.amount_rial) == debt.principal_rial,
        }
        for t in rows[:limit]
    ]
