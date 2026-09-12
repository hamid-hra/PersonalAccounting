from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select

from app.api.deps import Auth, DB
from app.enums import CategorizedBy
from app.models import Category, Contact, Transaction
from app.services.jalali import parse_jalali_date
from app.services.normalize import normalize

router = APIRouter()


def serialize(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "jalali_datetime": tx.jalali_datetime,
        "jalali_year": tx.jalali_year,
        "jalali_month": tx.jalali_month,
        "occurred_at": tx.occurred_at.isoformat(),
        "amount_rial": tx.amount_rial,
        "direction": tx.direction,
        "balance_after_rial": tx.balance_after_rial,
        "bank_tx_type": tx.bank_tx_type,
        "description_raw": tx.description_raw,
        "counterparty_name": tx.counterparty_name,
        "counterparty_bank": tx.counterparty_bank,
        "terminal_id": tx.terminal_id,
        "terminal_kind": tx.terminal_kind,
        "counterparty_card": tx.counterparty_card,
        "counterparty_iban": tx.counterparty_iban,
        "deposit_no": tx.deposit_no,
        "phone_number": tx.phone_number,
        "biller_id": tx.biller_id,
        "loan_ref": tx.loan_ref,
        "category_id": tx.category_id,
        "category_name": tx.category.name_fa if tx.category else None,
        "category_color": tx.category.color if tx.category else None,
        "contact_id": tx.contact_id,
        "contact_name": tx.contact.name_fa if tx.contact else None,
        "categorized_by": tx.categorized_by,
        "is_self_transfer": tx.is_self_transfer,
        "is_transfer": tx.is_transfer,
        "needs_review": tx.needs_review,
        "note": tx.note,
    }


def apply_filters(
    stmt: Select,
    *,
    account_id: int | None,
    category_id: int | None,
    contact_id: int | None,
    direction: str | None,
    from_jalali: str | None,
    to_jalali: str | None,
    q: str | None,
    min_rial: int | None,
    max_rial: int | None,
    needs_review: bool | None,
    include_self: bool,
    bank_tx_type: str | None,
) -> Select:
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if contact_id:
        stmt = stmt.where(Transaction.contact_id == contact_id)
    if direction:
        stmt = stmt.where(Transaction.direction == direction)
    if bank_tx_type:
        stmt = stmt.where(Transaction.bank_tx_type == bank_tx_type)
    if from_jalali:
        stmt = stmt.where(Transaction.occurred_date >= parse_jalali_date(from_jalali))
    if to_jalali:
        stmt = stmt.where(Transaction.occurred_date <= parse_jalali_date(to_jalali))
    if min_rial is not None:
        stmt = stmt.where(func.abs(Transaction.amount_rial) >= min_rial)
    if max_rial is not None:
        stmt = stmt.where(func.abs(Transaction.amount_rial) <= max_rial)
    if needs_review is not None:
        stmt = stmt.where(Transaction.needs_review.is_(needs_review))
    if not include_self:
        stmt = stmt.where(Transaction.is_self_transfer.is_(False))
    if q:
        needle = f"%{normalize(q)}%"
        stmt = stmt.where(
            or_(
                Transaction.description_norm.ilike(needle),
                Transaction.counterparty_name.ilike(needle),
                Transaction.terminal_id.ilike(f"%{q}%"),
            )
        )
    return stmt


@router.get("")
def list_transactions(
    db: DB,
    user: Auth,
    account_id: int | None = None,
    category_id: int | None = None,
    contact_id: int | None = None,
    direction: str | None = None,
    from_jalali: str | None = None,
    to_jalali: str | None = None,
    q: str | None = None,
    min_rial: int | None = None,
    max_rial: int | None = None,
    needs_review: bool | None = None,
    include_self: bool = True,
    bank_tx_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> dict:
    filters = dict(
        account_id=account_id,
        category_id=category_id,
        contact_id=contact_id,
        direction=direction,
        from_jalali=from_jalali,
        to_jalali=to_jalali,
        q=q,
        min_rial=min_rial,
        max_rial=max_rial,
        needs_review=needs_review,
        include_self=include_self,
        bank_tx_type=bank_tx_type,
    )

    totals = apply_filters(
        select(
            func.count(Transaction.id),
            func.coalesce(
                func.sum(func.greatest(Transaction.amount_rial, 0)), 0
            ),
            func.coalesce(
                func.sum(func.greatest(-Transaction.amount_rial, 0)), 0
            ),
        ),
        **filters,
    )
    total, sum_in, sum_out = db.execute(totals).one()

    stmt = apply_filters(select(Transaction), **filters)
    stmt = (
        stmt.order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [serialize(tx) for tx in db.scalars(stmt)]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "sum_in_rial": int(sum_in),
        "sum_out_rial": int(sum_out),
    }


class TxPatch(BaseModel):
    category_id: int | None = None
    contact_id: int | None = None
    note: str | None = None
    needs_review: bool | None = None
    is_self_transfer: bool | None = None


@router.patch("/{tx_id}")
def update_transaction(tx_id: int, payload: TxPatch, db: DB, user: Auth) -> dict:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تراکنش پیدا نشد.")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        tx.category_id = data["category_id"]
        tx.categorized_by = CategorizedBy.MANUAL
        tx.needs_review = False
    if "contact_id" in data:
        tx.contact_id = data["contact_id"]
    if "note" in data:
        tx.note = data["note"]
    if "needs_review" in data:
        tx.needs_review = data["needs_review"]
    if "is_self_transfer" in data:
        tx.is_self_transfer = data["is_self_transfer"]
        tx.is_transfer = tx.is_transfer or data["is_self_transfer"]

    db.commit()
    return serialize(tx)


class BulkCategorize(BaseModel):
    transaction_ids: list[int]
    category_id: int | None = None
    contact_id: int | None = None


@router.post("/bulk-categorize")
def bulk_categorize(payload: BulkCategorize, db: DB, user: Auth) -> dict:
    if not payload.transaction_ids:
        return {"updated": 0}
    rows = db.scalars(
        select(Transaction).where(Transaction.id.in_(payload.transaction_ids))
    ).all()
    for tx in rows:
        if payload.category_id is not None:
            tx.category_id = payload.category_id
            tx.categorized_by = CategorizedBy.MANUAL
            tx.needs_review = False
        if payload.contact_id is not None:
            tx.contact_id = payload.contact_id
    db.commit()
    return {"updated": len(rows)}


@router.get("/bank-types")
def bank_types(db: DB, user: Auth) -> list[dict]:
    rows = db.execute(
        select(Transaction.bank_tx_type, func.count())
        .where(Transaction.bank_tx_type.is_not(None))
        .group_by(Transaction.bank_tx_type)
        .order_by(func.count().desc())
    ).all()
    return [{"type": t, "count": c} for t, c in rows]
