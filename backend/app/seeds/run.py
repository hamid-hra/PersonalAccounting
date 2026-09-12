"""کاشت دادهٔ اولیه — idempotent، در هر بالا آمدن سرویس اجرا می‌شود."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import AppSetting, Category, Rule
from app.seeds.data import CATEGORIES, DEFAULT_SETTINGS, TYPE_RULES
from app.services import appsettings


def seed_categories(db: Session) -> dict[str, Category]:
    existing = {c.slug: c for c in db.scalars(select(Category))}
    for order, (slug, name, parent, kind, color, icon) in enumerate(CATEGORIES):
        cat = existing.get(slug)
        if cat is None:
            cat = Category(slug=slug, name_fa=name, kind=kind, color=color, icon=icon)
            cat.is_system = True
            cat.sort_order = order
            db.add(cat)
            existing[slug] = cat
    db.flush()

    # والدها در گذر دوم وصل می‌شوند تا ترتیب تعریف مهم نباشد
    for slug, _n, parent, *_ in CATEGORIES:
        if parent and existing[slug].parent_id is None:
            existing[slug].parent_id = existing[parent].id
    db.flush()
    return existing


def seed_rules(db: Session, cats: dict[str, Category]) -> None:
    have = {r.name for r in db.scalars(select(Rule).where(Rule.is_system.is_(True)))}
    for name, tx_type, cat_slug, review, is_transfer, priority in TYPE_RULES:
        if name in have:
            continue
        db.add(
            Rule(
                name=name,
                priority=priority,
                is_system=True,
                is_active=True,
                match_bank_tx_type=tx_type,
                set_category_id=cats[cat_slug].id,
                set_needs_review=review,
                set_is_transfer=is_transfer,
            )
        )
    db.flush()


def seed_settings(db: Session) -> None:
    have = {s.key for s in db.scalars(select(AppSetting))}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in have:
            db.add(AppSetting(key=key, value=value))
    db.flush()


def main() -> None:
    with SessionLocal() as db:
        cats = seed_categories(db)
        seed_rules(db, cats)
        seed_settings(db)
        db.commit()
        moved = appsettings.bootstrap_from_env(db)
    print(f"دسته‌ها: {len(CATEGORIES)} — قوانین: {len(TYPE_RULES)}")
    if moved:
        print(f"تنظیمات منتقل‌شده به دیتابیس: {', '.join(moved)}")


if __name__ == "__main__":
    main()
