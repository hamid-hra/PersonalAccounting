"""
لیست موارد مورد نیاز.

چیزهایی که لازم دارم، با برآورد قیمت و ددلاین. بعد از خرید می‌شود به
تراکنش بانکی وصلش کرد تا معلوم شود واقعاً چقدر درآمد در برابر برآورد.
"""

import hashlib
import shutil
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.config import settings
from app.enums import WISH_PRIORITY_LABELS_FA, WISH_PRIORITY_ORDER, WishPriority
from app.models import Transaction, WishItem
from app.services.jalali import parse_jalali_date, to_jalali_str

router = APIRouter()

ALLOWED_IMAGE = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def images_dir() -> Path:
    path = settings.data_dir / "wishlist"
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialize(w: WishItem) -> dict:
    today = date.today()
    days_left = (w.deadline_date - today).days if w.deadline_date else None
    actual = w.actual_rial
    return {
        "id": w.id,
        "title": w.title,
        "estimated_rial": w.estimated_rial,
        "actual_rial": actual,
        "difference_rial": (actual - w.estimated_rial)
        if (actual is not None and w.estimated_rial)
        else None,
        "priority": w.priority,
        "priority_label": WISH_PRIORITY_LABELS_FA.get(WishPriority(w.priority), w.priority),
        "category_id": w.category_id,
        "category_name": w.category.name_fa if w.category else None,
        "deadline_jalali": w.deadline_jalali,
        "days_left": days_left,
        "is_overdue": days_left is not None and days_left < 0 and not w.is_bought,
        "is_soon": days_left is not None and 0 <= days_left <= 14 and not w.is_bought,
        "url": w.url,
        "image_url": f"/api/wishlist/{w.id}/image" if w.image_name else None,
        "is_bought": w.is_bought,
        "bought_jalali": w.bought_jalali,
        "bought_transaction_id": w.bought_transaction_id,
        "note": w.note,
    }


def _sorted(items: list[WishItem]) -> list[WishItem]:
    """
    خریده‌نشده‌ها اول؛ بعد اولویت؛ بعد ددلاین نزدیک‌تر.
    مواردی که ددلاین ندارند آخرِ گروه خودشان می‌آیند.
    """
    return sorted(
        items,
        key=lambda w: (
            w.is_bought,
            WISH_PRIORITY_ORDER.get(WishPriority(w.priority), 9),
            w.deadline_date or date.max,
            -(w.estimated_rial or 0),
        ),
    )


@router.get("/priorities")
def priorities(user: Auth) -> list[dict]:
    return [
        {"value": p.value, "label": WISH_PRIORITY_LABELS_FA[p]} for p in WishPriority
    ]


@router.get("")
def list_items(db: DB, user: Auth, include_bought: bool = True) -> dict:
    stmt = select(WishItem)
    if not include_bought:
        stmt = stmt.where(WishItem.is_bought.is_(False))
    items = _sorted(list(db.scalars(stmt)))
    open_items = [w for w in items if not w.is_bought]
    return {
        "items": [serialize(w) for w in items],
        "open_count": len(open_items),
        "open_total_rial": sum(w.estimated_rial or 0 for w in open_items),
        "overdue_count": sum(
            1
            for w in open_items
            if w.deadline_date and w.deadline_date < date.today()
        ),
    }


class WishIn(BaseModel):
    title: str
    estimated_rial: int | None = None
    priority: str = WishPriority.NICE
    category_id: int | None = None
    deadline_jalali: str | None = None
    url: str | None = None
    note: str | None = None


def _apply(w: WishItem, data: dict) -> None:
    for field in ("title", "estimated_rial", "priority", "category_id", "url", "note"):
        if field in data:
            setattr(w, field, data[field])
    if "deadline_jalali" in data:
        raw = (data["deadline_jalali"] or "").strip()
        if raw:
            try:
                w.deadline_date = parse_jalali_date(raw)
            except ValueError as exc:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
            w.deadline_jalali = raw
        else:
            w.deadline_jalali = None
            w.deadline_date = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_item(payload: WishIn, db: DB, user: Auth) -> dict:
    if not payload.title.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "عنوان لازم است.")
    if payload.priority not in {p.value for p in WishPriority}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اولویت معتبر نیست.")
    item = WishItem(title=payload.title.strip())
    _apply(item, payload.model_dump(exclude={"title"}))
    db.add(item)
    db.commit()
    return serialize(item)


class WishPatch(BaseModel):
    title: str | None = None
    estimated_rial: int | None = None
    priority: str | None = None
    category_id: int | None = None
    deadline_jalali: str | None = None
    url: str | None = None
    note: str | None = None


@router.patch("/{item_id}")
def update_item(item_id: int, payload: WishPatch, db: DB, user: Auth) -> dict:
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    _apply(item, payload.model_dump(exclude_unset=True))
    db.commit()
    return serialize(item)


class BuyIn(BaseModel):
    transaction_id: int | None = None
    bought_jalali: str | None = None


@router.post("/{item_id}/bought")
def mark_bought(item_id: int, payload: BuyIn, db: DB, user: Auth) -> dict:
    """
    «خریدم». اگر تراکنش بانکی‌اش را هم بدهی، قیمت واقعی در برابر برآورد
    دیده می‌شود.
    """
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")

    tx = None
    if payload.transaction_id is not None:
        tx = db.get(Transaction, payload.transaction_id)
        if tx is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "تراکنش پیدا نشد.")

    item.is_bought = True
    item.bought_transaction_id = tx.id if tx else None
    item.bought_jalali = (
        payload.bought_jalali
        or (tx.jalali_datetime.split(" ")[0] if tx else to_jalali_str(date.today()))
    )
    db.commit()
    return serialize(item)


@router.post("/{item_id}/unbought")
def mark_unbought(item_id: int, db: DB, user: Auth) -> dict:
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    item.is_bought = False
    item.bought_transaction_id = None
    item.bought_jalali = None
    db.commit()
    return serialize(item)


@router.get("/{item_id}/suggest-transactions")
def suggest_transactions(item_id: int, db: DB, user: Auth, limit: int = 12) -> list[dict]:
    """
    تراکنش‌های خروجیِ نزدیک به برآورد قیمت — برای وصل‌کردن «خریدم».
    اگر برآوردی نباشد، آخرین خرج‌ها برمی‌گردند.
    """
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")

    stmt = select(Transaction).where(
        Transaction.amount_rial < 0,
        Transaction.is_self_transfer.is_(False),
        Transaction.is_reversed.is_(False),
    )
    if item.estimated_rial:
        # مبلغ‌ها منفی‌اند، پس بازه هم منفی می‌شود: بین ‎-۱.۸× و ‎-۰.۵× برآورد
        low = int(item.estimated_rial * 0.5)
        high = int(item.estimated_rial * 1.8)
        stmt = stmt.where(
            Transaction.amount_rial <= -low,
            Transaction.amount_rial >= -high,
        )
    rows = db.scalars(stmt.order_by(Transaction.occurred_at.desc()).limit(limit))
    return [
        {
            "id": t.id,
            "jalali_datetime": t.jalali_datetime,
            "amount_rial": t.amount_rial,
            "description": t.description_raw[:120],
            "category_name": t.category.name_fa if t.category else None,
        }
        for t in rows
    ]



@router.post("/{item_id}/image", status_code=status.HTTP_201_CREATED)
def upload_image(
    item_id: int,
    db: DB,
    user: Auth,
    file: UploadFile = File(...),
) -> dict:
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    if file.content_type not in ALLOWED_IMAGE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط عکس (png/jpg/webp/gif).")

    data = file.file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "عکس نباید از ۸ مگابایت بزرگ‌تر باشد.")

    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(file.filename or "").suffix.lower() or ".png"
    name = f"{digest}{suffix}"
    (images_dir() / name).write_bytes(data)

    item.image_name = name
    db.commit()
    return serialize(item)


@router.get("/{item_id}/image")
def get_image(item_id: int, db: DB, user: Auth):
    item = db.get(WishItem, item_id)
    if item is None or not item.image_name:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "عکسی نیست.")
    path = (images_dir() / item.image_name).resolve()
    if path.parent != images_dir().resolve() or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.")
    return FileResponse(path)


@router.delete("/{item_id}")
def delete_item(item_id: int, db: DB, user: Auth) -> dict:
    item = db.get(WishItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مورد پیدا نشد.")
    db.delete(item)
    db.commit()
    return {"ok": True}

