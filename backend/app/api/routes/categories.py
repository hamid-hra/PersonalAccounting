from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import Auth, DB
from app.enums import CategoryKind
from app.models import Category, Transaction
from app.services.normalize import fold

router = APIRouter()


def serialize(c: Category, usage: dict[int, int]) -> dict:
    return {
        "id": c.id,
        "slug": c.slug,
        "name_fa": c.name_fa,
        "parent_id": c.parent_id,
        "kind": c.kind,
        "color": c.color,
        "icon": c.icon,
        "is_system": c.is_system,
        "sort_order": c.sort_order,
        "transaction_count": usage.get(c.id, 0),
    }


def _unique_slug(db, base: str) -> str:
    """اگر نام تکراری بود، پسوند عددی می‌گیرد."""
    slug, n = base, 1
    while db.scalar(select(Category).where(Category.slug == slug)):
        n += 1
        slug = f"{base}_{n}"
    return slug


@router.get("")
def list_categories(db: DB, user: Auth) -> list[dict]:
    usage = dict(
        db.execute(
            select(Transaction.category_id, func.count()).group_by(Transaction.category_id)
        ).all()
    )
    cats = db.scalars(select(Category).order_by(Category.sort_order, Category.id))
    return [serialize(c, usage) for c in cats]


class CategoryIn(BaseModel):
    name_fa: str
    parent_id: int | None = None
    kind: str = CategoryKind.EXPENSE
    color: str = "#64748b"
    icon: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryIn, db: DB, user: Auth) -> dict:
    name = payload.name_fa.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نام دسته لازم است.")

    slug = _unique_slug(db, fold(name).replace(" ", "_")[:60] or "cat")

    cat = Category(
        slug=slug,
        name_fa=name,
        parent_id=payload.parent_id,
        kind=payload.kind,
        color=payload.color,
        icon=payload.icon,
        is_system=False,
        sort_order=500,
    )
    db.add(cat)
    db.commit()
    return serialize(cat, {})


class CategoryPatch(BaseModel):
    name_fa: str | None = None
    parent_id: int | None = None
    color: str | None = None
    icon: str | None = None
    kind: str | None = None


@router.patch("/{cat_id}")
def update_category(cat_id: int, payload: CategoryPatch, db: DB, user: Auth) -> dict:
    cat = db.get(Category, cat_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته پیدا نشد.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    return serialize(cat, {})


@router.delete("/{cat_id}")
def delete_category(cat_id: int, db: DB, user: Auth) -> dict:
    cat = db.get(Category, cat_id)
    if cat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته پیدا نشد.")
    if cat.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته‌های سیستمی حذف نمی‌شوند.")
    db.delete(cat)
    db.commit()
    return {"ok": True}
