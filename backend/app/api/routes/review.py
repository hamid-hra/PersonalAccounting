"""
صف بررسی — مهم‌ترین صفحهٔ برنامه.

فایل بانک نام فروشگاه را نمی‌دهد؛ فقط شمارهٔ پایانه. اما پول به‌شکل بسیار
نامتوازنی پخش شده (در نمونهٔ واقعی ۴ پایانه از ۲۰۵ پایانه، ۴۷ از ۶۶ میلیون
تومان خرید اینترنتی را می‌سازند). پس تراکنش‌های بی‌دسته بر اساس شناسه گروه
می‌شوند و به‌ترتیب «جمع مبلغ» مرتب — با برچسب‌زدن چند گروه اولِ فهرست،
بیشترِ پول معنا پیدا می‌کند.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import case, func, select, update

from app.api.deps import Auth, DB
from app.enums import IDENTIFIER_LABELS_FA, IdentifierKind
from app.models import Category, Contact, ContactIdentifier, Transaction
from app.services.categorize import apply_contact_to_matching
from app.services.normalize import fold_name

router = APIRouter()

_GROUP_KIND = case(
    (Transaction.terminal_id.is_not(None), Transaction.terminal_kind),
    (Transaction.counterparty_card.is_not(None), "card"),
    (Transaction.counterparty_iban.is_not(None), "iban"),
    (Transaction.deposit_no.is_not(None), "deposit_no"),
    (Transaction.biller_id.is_not(None), "biller_id"),
    (Transaction.phone_number.is_not(None), "phone"),
    else_="other",
)

_KIND_LABELS: dict[str, str] = {k.value: v for k, v in IDENTIFIER_LABELS_FA.items()} | {
    "other": "بدون شناسه"
}

_GROUP_VALUE = func.coalesce(
    Transaction.terminal_id,
    Transaction.counterparty_card,
    Transaction.counterparty_iban,
    Transaction.deposit_no,
    Transaction.biller_id,
    Transaction.phone_number,
    Transaction.bank_tx_type,
)


@router.get("/groups")
def review_groups(
    db: DB,
    user: Auth,
    limit: int = Query(60, ge=1, le=300),
    direction: str | None = None,
    sort: str = Query("amount", pattern="^(amount|date|count)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    """
    گروه‌های بی‌دسته.

    پیش‌فرض پرخرج‌ترین اول است (بیشترین پول با کمترین کار برچسب می‌خورد)،
    ولی مرتب‌سازی بر اساس تاریخ برای رسیدگی به تراکنش‌های تازه هم لازم است.
    """
    base = select(
            _GROUP_KIND.label("kind"),
            _GROUP_VALUE.label("value"),
            func.count().label("count"),
            func.sum(func.abs(Transaction.amount_rial)).label("total_rial"),
            func.min(Transaction.jalali_datetime).label("first_seen"),
            func.max(Transaction.jalali_datetime).label("last_seen"),
            func.max(Transaction.counterparty_name).label("suggested_name"),
            func.max(Transaction.bank_tx_type).label("bank_tx_type"),
            func.max(Transaction.description_raw).label("sample"),
    ).where(
        Transaction.needs_review.is_(True),
        Transaction.is_self_transfer.is_(False),
        Transaction.is_reversed.is_(False),
    )

    if direction:
        base = base.where(Transaction.direction == direction)

    sort_column = {
        "amount": func.sum(func.abs(Transaction.amount_rial)),
        "date": func.max(Transaction.occurred_at),
        "count": func.count(),
    }[sort]
    stmt = (
        base.group_by("kind", "value")
        .order_by(sort_column.asc() if order == "asc" else sort_column.desc())
        .limit(limit)
    )

    groups = []
    for row in db.execute(stmt):
        kind = row.kind or "other"
        groups.append(
            {
                "kind": kind,
                "kind_label": _KIND_LABELS.get(kind, "سایر"),
                "value": row.value,
                "count": row.count,
                "total_rial": int(row.total_rial or 0),
                "first_seen": row.first_seen,
                "last_seen": row.last_seen,
                "suggested_name": row.suggested_name,
                "bank_tx_type": row.bank_tx_type,
                "sample": row.sample,
                "labelable": kind != "other",
            }
        )

    pending = db.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.needs_review.is_(True),
            Transaction.is_self_transfer.is_(False),
            Transaction.is_reversed.is_(False),
        )
    )
    pending_rial = db.scalar(
        select(func.coalesce(func.sum(func.abs(Transaction.amount_rial)), 0)).where(
            Transaction.needs_review.is_(True),
            Transaction.is_self_transfer.is_(False),
            Transaction.is_reversed.is_(False),
        )
    )
    return {
        "groups": groups,
        "pending_transactions": pending or 0,
        "pending_rial": int(pending_rial or 0),
    }


class LabelIn(BaseModel):
    kind: str
    value: str
    contact_name: str
    category_id: int | None = None


@router.post("/label")
def label_group(payload: LabelIn, db: DB, user: Auth) -> dict:
    """
    یک گروه را به فروشنده نسبت می‌دهد و بلافاصله روی همهٔ تراکنش‌های
    گذشتهٔ همان شناسه اعمال می‌کند.
    """
    valid_kinds = {k.value for k in IdentifierKind}
    if payload.kind not in valid_kinds:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع شناسه معتبر نیست.")

    name = payload.contact_name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نام فروشنده لازم است.")

    if payload.category_id is not None and db.get(Category, payload.category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته پیدا نشد.")

    name_norm = fold_name(name)
    contact = db.scalar(select(Contact).where(Contact.name_norm == name_norm))
    if contact is None:
        contact = Contact(name_fa=name, name_norm=name_norm, category_id=payload.category_id)
        db.add(contact)
        db.flush()
    elif payload.category_id is not None:
        contact.category_id = payload.category_id

    existing = db.scalar(
        select(ContactIdentifier).where(
            ContactIdentifier.kind == payload.kind, ContactIdentifier.value == payload.value
        )
    )
    if existing is None:
        db.add(
            ContactIdentifier(
                contact_id=contact.id, kind=payload.kind, value=payload.value
            )
        )
    else:
        existing.contact_id = contact.id
    db.commit()

    updated = apply_contact_to_matching(db, payload.kind, payload.value, contact)
    return {
        "contact_id": contact.id,
        "contact_name": contact.name_fa,
        "transactions_updated": updated,
    }


# ---------------------------------------------------------------- خواندن همه
@router.post("/dismiss-all")
def dismiss_all(db: DB, user: Auth) -> dict:
    """
    همهٔ موارد معلق را «خوانده» علامت می‌زند.

    دستهٔ تراکنش‌ها دست‌نخورده می‌ماند («بدون دسته») و از فیلتر صفحهٔ
    تراکنش‌ها همچنان پیدا می‌شوند — چیزی حذف نمی‌شود، فقط از صف بیرون
    می‌رود تا از این به بعد فقط فایل‌های تازه در صف بیایند.
    """
    result = db.execute(
        update(Transaction)
        .where(
            Transaction.needs_review.is_(True),
            Transaction.is_self_transfer.is_(False),
            Transaction.is_reversed.is_(False),
        )
        .values(needs_review=False)
    )
    db.commit()
    return {"dismissed": result.rowcount or 0}


# ---------------------------------------------------------------- صف درآمد
@router.get("/income")
def income_queue(db: DB, user: Auth, limit: int = Query(60, ge=1, le=300)) -> dict:
    """
    واریزی‌هایی که هنوز مشخص نیست درآمد هستند یا نه.

    هر واریزی درآمد نیست — وام، پس‌گرفتن قرض و انتقال از حساب دیگران هم
    واریز می‌شوند. تا وقتی تصمیم نگرفته باشی، در هیچ آماری شمرده نمی‌شوند.
    گروه‌بندی بر اساس طرف‌حساب است تا با یک تصمیم چند تراکنش تعیین‌تکلیف شود.
    """
    base = select(Transaction).where(
        Transaction.amount_rial > 0,
        Transaction.is_income.is_(None),
        Transaction.is_self_transfer.is_(False),
        Transaction.is_reversed.is_(False),
    )
    rows = list(db.scalars(base))

    groups: dict[tuple[str, str], dict] = {}
    for tx in rows:
        key = _income_key(tx)
        entry = groups.setdefault(
            key,
            {
                "kind": key[0],
                "value": key[1],
                "label": _income_label(tx, key),
                "count": 0,
                "total_rial": 0,
                "first_jalali": tx.jalali_datetime,
                "last_jalali": tx.jalali_datetime,
                "sample_note": tx.note,
                "bank_tx_type": tx.bank_tx_type,
                "transaction_ids": [],
            },
        )
        entry["count"] += 1
        entry["total_rial"] += tx.amount_rial
        entry["transaction_ids"].append(tx.id)
        entry["first_jalali"] = min(entry["first_jalali"], tx.jalali_datetime)
        entry["last_jalali"] = max(entry["last_jalali"], tx.jalali_datetime)
        if tx.note and not entry["sample_note"]:
            entry["sample_note"] = tx.note

    ordered = sorted(groups.values(), key=lambda g: g["total_rial"], reverse=True)[:limit]
    return {
        "pending_count": len(rows),
        "pending_rial": sum(t.amount_rial for t in rows),
        "groups": ordered,
    }


def _income_key(tx: Transaction) -> tuple[str, str]:
    for kind, value in (
        ("iban", tx.counterparty_iban),
        ("card", tx.counterparty_card),
        ("deposit_no", tx.deposit_no),
        ("name", tx.counterparty_name_norm),
    ):
        if value:
            return kind, value
    return "bank_tx_type", tx.bank_tx_type or "بدون شناسه"


def _income_label(tx: Transaction, key: tuple[str, str]) -> str:
    return tx.counterparty_name or tx.bank_tx_type or key[1]


class IncomeDecision(BaseModel):
    is_income: bool
    transaction_ids: list[int] | None = None
    kind: str | None = None
    value: str | None = None


@router.post("/income/decide")
def decide_income(payload: IncomeDecision, db: DB, user: Auth) -> dict:
    """
    «این درآمد است» یا «درآمد نیست» — برای یک تراکنش یا کل یک طرف‌حساب.
    """
    stmt = update(Transaction).values(is_income=payload.is_income)

    if payload.transaction_ids:
        stmt = stmt.where(Transaction.id.in_(payload.transaction_ids))
    elif payload.kind and payload.value:
        column = {
            "iban": Transaction.counterparty_iban,
            "card": Transaction.counterparty_card,
            "deposit_no": Transaction.deposit_no,
            "name": Transaction.counterparty_name_norm,
            "bank_tx_type": Transaction.bank_tx_type,
        }.get(payload.kind)
        if column is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع شناسه معتبر نیست.")
        stmt = stmt.where(column == payload.value, Transaction.amount_rial > 0)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "یا فهرست تراکنش بده یا شناسهٔ طرف‌حساب."
        )

    result = db.execute(stmt)
    db.commit()
    return {"updated": result.rowcount or 0}
