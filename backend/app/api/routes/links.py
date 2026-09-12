from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.models import Transaction, TxLink
from app.services import links as svc

router = APIRouter()

KIND_LABELS = {
    "cross_account": "انتقال بین حساب‌های خودم",
    "reversal": "حوالهٔ برگشتی",
    "fee": "کارمزد",
}


def _tx_brief(tx: Transaction | None) -> dict | None:
    if tx is None:
        return None
    return {
        "id": tx.id,
        "account_id": tx.account_id,
        "account_title": tx.account.title if tx.account else None,
        "jalali_datetime": tx.jalali_datetime,
        "amount_rial": tx.amount_rial,
        "direction": tx.direction,
        "bank_tx_type": tx.bank_tx_type,
        "description_raw": tx.description_raw[:160],
    }


@router.post("/detect")
def detect(db: DB, user: Auth) -> dict:
    """کشف دوبارهٔ پیوندها روی کل تراکنش‌ها."""
    created = svc.detect_links(db)
    return {"created": created, "summary": svc.link_summary(db)}


@router.get("/summary")
def summary(db: DB, user: Auth) -> dict:
    return svc.link_summary(db)


@router.get("")
def list_links(
    db: DB,
    user: Auth,
    kind: str | None = None,
    only_unconfirmed: bool = False,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict]:
    stmt = select(TxLink).where(TxLink.is_rejected.is_(False))
    if kind:
        stmt = stmt.where(TxLink.kind == kind)
    if only_unconfirmed:
        stmt = stmt.where(TxLink.is_confirmed.is_(False))
    stmt = stmt.order_by(TxLink.amount_rial.desc()).limit(limit)

    out = []
    for link in db.scalars(stmt):
        out.append(
            {
                "id": link.id,
                "kind": link.kind,
                "kind_label": KIND_LABELS.get(link.kind, link.kind),
                "amount_rial": link.amount_rial,
                "seconds_apart": link.seconds_apart,
                "confidence": link.confidence,
                "matched_by": link.matched_by,
                "is_confirmed": link.is_confirmed,
                "primary": _tx_brief(db.get(Transaction, link.primary_tx_id)),
                "secondary": _tx_brief(db.get(Transaction, link.secondary_tx_id)),
            }
        )
    return out


@router.post("/{link_id}/confirm")
def confirm(link_id: int, db: DB, user: Auth) -> dict:
    link = db.get(TxLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیوند پیدا نشد.")
    link.is_confirmed = True
    link.is_rejected = False
    db.commit()
    svc.apply_links(db)
    return {"ok": True}


@router.post("/{link_id}/reject")
def reject(link_id: int, db: DB, user: Auth) -> dict:
    """این دو تراکنش به هم ربطی ندارند — اثرشان برداشته شود."""
    link = db.get(TxLink, link_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیوند پیدا نشد.")
    link.is_rejected = True
    link.is_confirmed = False
    db.commit()
    svc.apply_links(db)
    return {"ok": True}
