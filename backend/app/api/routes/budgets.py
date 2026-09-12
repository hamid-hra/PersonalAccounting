from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.models import Budget, Category
from app.services import analytics

router = APIRouter()


@router.get("")
def list_budgets(db: DB, user: Auth) -> list[dict]:
    out = []
    for b in db.scalars(select(Budget)):
        cat = db.get(Category, b.category_id)
        out.append(
            {
                "id": b.id,
                "category_id": b.category_id,
                "category_name": cat.name_fa if cat else "—",
                "jalali_year": b.jalali_year,
                "jalali_month": b.jalali_month,
                "amount_rial": b.amount_rial,
            }
        )
    return out


@router.get("/status")
def status_endpoint(db: DB, user: Auth, year: int | None = None, month: int | None = None) -> list[dict]:
    return analytics.budget_status(db, year, month)


class BudgetIn(BaseModel):
    category_id: int
    amount_rial: int
    jalali_year: int | None = None
    jalali_month: int | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def upsert_budget(payload: BudgetIn, db: DB, user: Auth) -> dict:
    if db.get(Category, payload.category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دسته پیدا نشد.")
    if payload.amount_rial < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ نمی‌تواند منفی باشد.")

    existing = db.scalar(
        select(Budget).where(
            Budget.category_id == payload.category_id,
            Budget.jalali_year.is_(payload.jalali_year)
            if payload.jalali_year is None
            else Budget.jalali_year == payload.jalali_year,
            Budget.jalali_month.is_(payload.jalali_month)
            if payload.jalali_month is None
            else Budget.jalali_month == payload.jalali_month,
        )
    )
    if existing:
        existing.amount_rial = payload.amount_rial
        db.commit()
        return {"id": existing.id, "updated": True}

    budget = Budget(**payload.model_dump())
    db.add(budget)
    db.commit()
    return {"id": budget.id, "updated": False}


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, db: DB, user: Auth) -> dict:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بودجه پیدا نشد.")
    db.delete(budget)
    db.commit()
    return {"ok": True}
