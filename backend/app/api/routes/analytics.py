from fastapi import APIRouter, Query

from app.api.deps import Auth, DB
from app.services import analytics
from app.services.jalali import month_range

router = APIRouter()


def _range(year: int | None, month: int | None):
    if year and month:
        return month_range(year, month)
    return None, None


@router.get("/summary")
def summary(db: DB, user: Auth, year: int | None = None, month: int | None = None) -> dict:
    return analytics.summary(db, year, month)


@router.get("/monthly")
def monthly(db: DB, user: Auth, months: int = Query(12, ge=1, le=60)) -> list[dict]:
    return analytics.monthly_series(db, months)


@router.get("/by-category")
def by_category(
    db: DB,
    user: Auth,
    year: int | None = None,
    month: int | None = None,
    direction: str = "out",
) -> list[dict]:
    start, end = _range(year, month)
    return analytics.by_category(db, start, end, direction)


@router.get("/top-contacts")
def top_contacts(
    db: DB, user: Auth, year: int | None = None, month: int | None = None, limit: int = 15
) -> list[dict]:
    start, end = _range(year, month)
    return analytics.top_contacts(db, start, end, limit)


@router.get("/top-counterparties")
def top_counterparties(
    db: DB, user: Auth, year: int | None = None, month: int | None = None, limit: int = 15
) -> list[dict]:
    start, end = _range(year, month)
    return analytics.by_counterparty(db, start, end, limit)


# ------------------------------------------------------------- هدررفت
@router.get("/insights/recurring")
def recurring(db: DB, user: Auth, min_occurrences: int = Query(3, ge=2, le=12)) -> list[dict]:
    return analytics.recurring(db, min_occurrences)


@router.get("/insights/micro-spend")
def micro_spend(db: DB, user: Auth) -> dict:
    return analytics.micro_spend(db)


@router.get("/insights/month-over-month")
def month_over_month(db: DB, user: Auth, lookback: int = Query(3, ge=1, le=12)) -> dict:
    return analytics.month_over_month(db, lookback)
