from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import Auth, DB
from app.enums import BANK_LABELS_FA, Bank
from app.models import Account, Transaction

router = APIRouter()


@router.get("")
def list_accounts(db: DB, user: Auth) -> list[dict]:
    counts = dict(
        db.execute(
            select(Transaction.account_id, func.count()).group_by(Transaction.account_id)
        ).all()
    )
    out = []
    for a in db.scalars(select(Account).order_by(Account.id)):
        out.append(
            {
                "id": a.id,
                "bank": a.bank,
                "bank_label": BANK_LABELS_FA.get(Bank(a.bank), a.bank),
                "title": a.title,
                "iban": a.iban,
                "account_number": a.account_number,
                "owner_name": a.owner_name,
                "opened_at_jalali": a.opened_at_jalali,
                "transaction_count": counts.get(a.id, 0),
            }
        )
    return out


@router.get("/banks")
def supported_banks(user: Auth) -> list[dict]:
    from app.importers import all_importers

    return [{"bank": i.bank, "label": i.label_fa} for i in all_importers()]
