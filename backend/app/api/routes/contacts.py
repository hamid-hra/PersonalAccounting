from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import Auth, DB
from app.enums import (
    CONTACT_KIND_LABELS_FA,
    IDENTIFIER_LABELS_FA,
    ContactKind,
    IdentifierKind,
)
from app.models import Contact, ContactIdentifier, Transaction
from app.services.categorize import apply_contact_to_matching
from app.services.normalize import fold_name, fold_name_key

router = APIRouter()

_KIND_LABELS = {k.value: v for k, v in IDENTIFIER_LABELS_FA.items()}


def serialize(m: Contact, stats: dict[int, tuple[int, int]]) -> dict:
    count, total = stats.get(m.id, (0, 0))
    return {
        "id": m.id,
        "name_fa": m.name_fa,
        "kind": m.kind,
        "kind_label": CONTACT_KIND_LABELS_FA.get(ContactKind(m.kind), m.kind),
        "category_id": m.category_id,
        "category_name": m.category.name_fa if m.category else None,
        "income_category_id": m.income_category_id,
        "income_category_name": m.income_category.name_fa if m.income_category else None,
        "phone": m.phone,
        "is_favorite": m.is_favorite,
        "note": m.note,
        "transaction_count": count,
        "total_rial": total,
        "identifiers": [
            {
                "id": i.id,
                "kind": i.kind,
                "kind_label": _KIND_LABELS.get(i.kind, i.kind),
                "value": i.value,
            }
            for i in m.identifiers
        ],
    }


def _stats(db) -> dict[int, tuple[int, int]]:
    rows = db.execute(
        select(
            Transaction.contact_id,
            func.count(),
            func.coalesce(func.sum(func.abs(Transaction.amount_rial)), 0),
        )
        .where(Transaction.contact_id.is_not(None))
        .group_by(Transaction.contact_id)
    ).all()
    return {mid: (c, int(t)) for mid, c, t in rows}


@router.get("")
def list_contacts(db: DB, user: Auth) -> list[dict]:
    stats = _stats(db)
    contacts = db.scalars(select(Contact).order_by(Contact.name_fa))
    return sorted(
        (serialize(m, stats) for m in contacts),
        key=lambda m: m["total_rial"],
        reverse=True,
    )


class ContactIn(BaseModel):
    name_fa: str
    kind: str = ContactKind.PERSON
    category_id: int | None = None
    # «اگر از این مخاطب پول آمد، حقوقم است»
    income_category_id: int | None = None
    phone: str | None = None
    note: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactIn, db: DB, user: Auth) -> dict:
    name = payload.name_fa.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نام فروشنده لازم است.")
    norm = fold_name(name)
    if db.scalar(select(Contact).where(Contact.name_norm == norm)):
        raise HTTPException(status.HTTP_409_CONFLICT, "فروشنده‌ای با این نام هست.")
    m = Contact(
        name_fa=name,
        name_norm=norm,
        name_key=fold_name_key(name),
        kind=payload.kind,
        category_id=payload.category_id,
        income_category_id=payload.income_category_id,
        phone=payload.phone,
        note=payload.note,
    )
    db.add(m)
    db.commit()
    return serialize(m, {})


class ContactPatch(BaseModel):
    name_fa: str | None = None
    kind: str | None = None
    category_id: int | None = None
    income_category_id: int | None = None
    phone: str | None = None
    is_favorite: bool | None = None
    note: str | None = None


@router.patch("/{contact_id}")
def update_contact(contact_id: int, payload: ContactPatch, db: DB, user: Auth) -> dict:
    m = db.get(Contact, contact_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فروشنده پیدا نشد.")
    data = payload.model_dump(exclude_unset=True)
    if "name_fa" in data and data["name_fa"]:
        m.name_fa = data["name_fa"].strip()
        m.name_norm = fold_name(m.name_fa)
        m.name_key = fold_name_key(m.name_fa)
    for field in ("kind", "category_id", "income_category_id", "phone", "is_favorite", "note"):
        if field in data:
            setattr(m, field, data[field])
    db.commit()

    # تغییر دستهٔ مخاطب باید روی همهٔ تراکنش‌هایش اثر کند
    if "category_id" in data or "income_category_id" in data:
        for ident in m.identifiers:
            apply_contact_to_matching(db, ident.kind, ident.value, m)
    return serialize(m, _stats(db))


@router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: DB, user: Auth) -> dict:
    m = db.get(Contact, contact_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فروشنده پیدا نشد.")
    db.query(Transaction).filter(Transaction.contact_id == contact_id).update(
        {"contact_id": None}
    )
    db.delete(m)
    db.commit()
    return {"ok": True}


class IdentifierIn(BaseModel):
    kind: str
    value: str


@router.post("/{contact_id}/identifiers", status_code=status.HTTP_201_CREATED)
def add_identifier(contact_id: int, payload: IdentifierIn, db: DB, user: Auth) -> dict:
    m = db.get(Contact, contact_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فروشنده پیدا نشد.")
    if payload.kind not in {k.value for k in IdentifierKind}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع شناسه معتبر نیست.")

    value = payload.value.strip()
    existing = db.scalar(
        select(ContactIdentifier).where(
            ContactIdentifier.kind == payload.kind, ContactIdentifier.value == value
        )
    )
    if existing:
        existing.contact_id = contact_id
    else:
        db.add(ContactIdentifier(contact_id=contact_id, kind=payload.kind, value=value))
    db.commit()
    updated = apply_contact_to_matching(db, payload.kind, value, m)
    return {"ok": True, "transactions_updated": updated}


@router.delete("/identifiers/{identifier_id}")
def delete_identifier(identifier_id: int, db: DB, user: Auth) -> dict:
    ident = db.get(ContactIdentifier, identifier_id)
    if ident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "شناسه پیدا نشد.")
    db.delete(ident)
    db.commit()
    return {"ok": True}


@router.get("/identifier-kinds")
def identifier_kinds(user: Auth) -> list[dict]:
    return [{"kind": k.value, "label": IDENTIFIER_LABELS_FA[k]} for k in IdentifierKind]


@router.get("/kinds")
def contact_kinds(user: Auth) -> list[dict]:
    return [{"kind": k.value, "label": CONTACT_KIND_LABELS_FA[k]} for k in ContactKind]


class FromTransactionIn(BaseModel):
    """ساخت مخاطب مستقیم از یک تراکنش — همهٔ شناسه‌هایش یکجا ثبت می‌شوند."""

    transaction_id: int
    name_fa: str | None = None
    kind: str = ContactKind.PERSON
    category_id: int | None = None
    income_category_id: int | None = None


@router.post("/from-transaction", status_code=status.HTTP_201_CREATED)
def create_from_transaction(payload: FromTransactionIn, db: DB, user: Auth) -> dict:
    """
    «این شماره کارت را ذخیره کن» — از داخل تراکنش.

    نام و همهٔ شناسه‌های موجود (کارت، شبا، سپرده، پایانه، تلفن) برداشته
    می‌شوند و تراکنش‌های گذشتهٔ همان شناسه‌ها بلافاصله وصل می‌شوند.
    """
    tx = db.get(Transaction, payload.transaction_id)
    if tx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تراکنش پیدا نشد.")

    name = (payload.name_fa or tx.counterparty_name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این تراکنش نام طرف مقابل ندارد؛ خودت یک نام بنویس.",
        )

    norm = fold_name(name)
    contact = db.scalar(select(Contact).where(Contact.name_norm == norm))
    if contact is None:
        contact = Contact(
            name_fa=name,
            name_norm=norm,
            name_key=fold_name_key(name),
            kind=payload.kind,
            category_id=payload.category_id,
            income_category_id=payload.income_category_id,
        )
        db.add(contact)
        db.flush()
    else:
        if payload.category_id is not None:
            contact.category_id = payload.category_id
        if payload.income_category_id is not None:
            contact.income_category_id = payload.income_category_id

    pairs: list[tuple[str, str]] = []
    if tx.terminal_id and tx.terminal_kind:
        pairs.append((tx.terminal_kind, tx.terminal_id))
    for kind, value in (
        ("card", tx.counterparty_card),
        ("iban", tx.counterparty_iban),
        ("deposit_no", tx.deposit_no),
        ("phone", tx.phone_number),
        ("biller_id", tx.biller_id),
    ):
        if value:
            pairs.append((kind, value))

    updated = 0
    for kind, value in pairs:
        existing = db.scalar(
            select(ContactIdentifier).where(
                ContactIdentifier.kind == kind, ContactIdentifier.value == value
            )
        )
        if existing is None:
            db.add(ContactIdentifier(contact_id=contact.id, kind=kind, value=value))
        else:
            existing.contact_id = contact.id
    db.commit()

    for kind, value in pairs:
        updated += apply_contact_to_matching(db, kind, value, contact)

    return {
        "contact_id": contact.id,
        "name_fa": contact.name_fa,
        "identifiers_added": len(pairs),
        "transactions_updated": updated,
    }
