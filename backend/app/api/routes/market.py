from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.models import AssetHolding, MarketItem, PriceAlert
from app.services import market as svc
from app.services.jalali import parse_jalali_date

router = APIRouter()


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, svc.QuotaExhausted):
        return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@router.get("/quota")
def quota(db: DB, user: Auth) -> dict:
    """چقدر از سهمیه مانده — قبل از هر درخواست دیده می‌شود."""
    return svc.quota_status(db)


@router.get("/items")
def items(db: DB, user: Auth) -> list[dict]:
    svc.seed_items(db)
    out = []
    for item in db.scalars(
        select(MarketItem).where(MarketItem.is_tracked).order_by(MarketItem.sort_order)
    ):
        price = svc.latest_price(db, item.code)
        out.append(
            {
                "code": item.code,
                "label_fa": item.label_fa,
                "kind": item.kind,
                "unit_fa": item.unit_fa,
                "is_tracked": item.is_tracked,
                "latest_rial": price.close_rial if price else None,
                "latest_date": price.jalali_date if price else None,
                "change_percent": float(price.change_percent)
                if price and price.change_percent is not None
                else None,
            }
        )
    return out


@router.get("/observations")
def observations(db: DB, user: Auth) -> list[dict]:
    """
    مشاهده‌های واقعی دربارهٔ قیمت‌ها.

    هرکدام یک جملهٔ قابل‌راستی‌آزمایی است — هیچ‌کدام توصیهٔ خرید یا فروش
    نیستند و دربارهٔ آینده چیزی نمی‌گویند.
    """
    return svc.observations(db)


@router.get("/items/{code}/stats")
def item_stats(code: str, db: DB, user: Auth) -> dict:
    return svc.item_stats(db, code)


@router.get("/items/{code}/series")
def item_series(code: str, db: DB, user: Auth, days: int = Query(365, ge=7, le=2000)) -> list[dict]:
    return [
        {
            "date": p.price_date.isoformat(),
            "jalali_date": p.jalali_date,
            "close_rial": p.close_rial,
            "open_rial": p.open_rial,
            "high_rial": p.high_rial,
            "low_rial": p.low_rial,
        }
        for p in svc.price_series(db, code, days)
    ]


@router.post("/refresh")
def refresh(db: DB, user: Auth) -> dict:
    """قیمت امروزِ همهٔ اقلام — یک درخواست."""
    try:
        return svc.refresh_prices(db)
    except (svc.QuotaExhausted, svc.MarketUnavailable) as exc:
        raise _fail(exc) from exc


@router.post("/items/{code}/backfill")
def backfill(code: str, db: DB, user: Auth, days: int = Query(365, ge=30, le=2000)) -> dict:
    """تاریخچهٔ یک قلم — یک درخواست برای کل بازه."""
    try:
        return svc.backfill_history(db, code, days)
    except (svc.QuotaExhausted, svc.MarketUnavailable) as exc:
        raise _fail(exc) from exc


# ---------------------------------------------------------------- هشدار
@router.get("/alerts")
def list_alerts(db: DB, user: Auth) -> list[dict]:
    return svc.active_alerts(db)


class AlertIn(BaseModel):
    item_code: str
    direction: str  # above | below
    threshold_rial: int
    note: str | None = None


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertIn, db: DB, user: Auth) -> list[dict]:
    if payload.direction not in {"above", "below"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "جهت هشدار معتبر نیست.")
    if db.get(MarketItem, payload.item_code) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این قلم در فهرست بازار نیست.")
    if payload.threshold_rial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "آستانه باید مثبت باشد.")
    db.add(
        PriceAlert(
            item_code=payload.item_code,
            direction=payload.direction,
            threshold_rial=payload.threshold_rial,
            note=payload.note,
        )
    )
    db.commit()
    svc.check_alerts(db)
    return svc.active_alerts(db)


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: int, db: DB, user: Auth) -> dict:
    alert = db.get(PriceAlert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "هشدار پیدا نشد.")
    db.delete(alert)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- سبد
@router.get("/portfolio")
def portfolio(db: DB, user: Auth) -> dict:
    return svc.portfolio(db)


class HoldingIn(BaseModel):
    item_code: str
    quantity: float
    acquired_jalali: str
    cost_rial: int | None = None
    transaction_id: int | None = None
    note: str | None = None


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
def add_holding(payload: HoldingIn, db: DB, user: Auth) -> dict:
    svc.seed_items(db)
    if db.get(MarketItem, payload.item_code) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این قلم در فهرست بازار نیست.")
    if payload.quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدار باید مثبت باشد.")
    try:
        acquired = parse_jalali_date(payload.acquired_jalali)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.add(
        AssetHolding(
            item_code=payload.item_code,
            quantity=payload.quantity,
            acquired_jalali=payload.acquired_jalali,
            acquired_date=acquired,
            cost_rial=payload.cost_rial,
            transaction_id=payload.transaction_id,
            note=payload.note,
        )
    )
    db.commit()
    return svc.portfolio(db)


@router.delete("/holdings/{holding_id}")
def delete_holding(holding_id: int, db: DB, user: Auth) -> dict:
    holding = db.get(AssetHolding, holding_id)
    if holding is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دارایی پیدا نشد.")
    db.delete(holding)
    db.commit()
    return {"ok": True}
