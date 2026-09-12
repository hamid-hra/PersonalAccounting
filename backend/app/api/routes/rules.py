from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.models import Rule
from app.services.categorize import recategorize_all

router = APIRouter()


def serialize(r: Rule) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "priority": r.priority,
        "is_active": r.is_active,
        "is_system": r.is_system,
        "match_bank_tx_type": r.match_bank_tx_type,
        "match_description_regex": r.match_description_regex,
        "match_counterparty_regex": r.match_counterparty_regex,
        "match_direction": r.match_direction,
        "match_amount_min": r.match_amount_min,
        "match_amount_max": r.match_amount_max,
        "set_category_id": r.set_category_id,
        "set_category_name": r.category.name_fa if r.category else None,
        "set_contact_id": r.set_contact_id,
        "set_is_transfer": r.set_is_transfer,
        "set_needs_review": r.set_needs_review,
    }


@router.get("")
def list_rules(db: DB, user: Auth) -> list[dict]:
    rules = db.scalars(select(Rule).order_by(Rule.is_system, Rule.priority, Rule.id))
    return [serialize(r) for r in rules]


class RuleIn(BaseModel):
    name: str
    priority: int = 50
    is_active: bool = True
    match_bank_tx_type: str | None = None
    match_description_regex: str | None = None
    match_counterparty_regex: str | None = None
    match_direction: str | None = None
    match_amount_min: int | None = None
    match_amount_max: int | None = None
    set_category_id: int | None = None
    set_contact_id: int | None = None
    set_is_transfer: bool | None = None
    set_needs_review: bool | None = False


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleIn, db: DB, user: Auth) -> dict:
    rule = Rule(**payload.model_dump(), is_system=False)
    db.add(rule)
    db.commit()
    recategorize_all(db)
    return serialize(rule)


@router.patch("/{rule_id}")
def update_rule(rule_id: int, payload: RuleIn, db: DB, user: Auth) -> dict:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قانون پیدا نشد.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    recategorize_all(db)
    return serialize(rule)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: DB, user: Auth) -> dict:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قانون پیدا نشد.")
    if rule.is_system:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "قوانین سیستمی حذف نمی‌شوند؛ غیرفعالشان کن.")
    db.delete(rule)
    db.commit()
    recategorize_all(db)
    return {"ok": True}
