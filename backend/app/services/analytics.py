"""
تحلیل‌ها.

قانون همیشگی: انتقال بین حساب‌های خودم هزینه نیست و از همهٔ محاسبه‌ها
کنار گذاشته می‌شود. در نمونهٔ واقعی این ۴۲٪ کل خروجی بود؛ بدون این فیلتر
هر عددی که نشان داده شود دو برابرِ واقعیت است.
"""

import re
import statistics
from collections import defaultdict
from datetime import date

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.enums import CategoryKind
from app.models import AppSetting, Budget, Category, Contact, Transaction
from app.services.jalali import (
    add_months,
    month_label,
    month_range,
    to_jalali_str,
    today_jalali_parts,
)

# خروجی از روی علامت مبلغ حساب می‌شود.
# با case نوشته شده نه greatest، چون greatest مخصوص پستگرس است و
# تست‌ها روی SQLite اجرا می‌شوند — منطق باید روی هر دو یکسان باشد.
_OUT = case((Transaction.amount_rial < 0, -Transaction.amount_rial), else_=0)

# ورودی اما فقط وقتی «درآمد» است که خودِ کاربر تأییدش کرده باشد.
# هر واریزی درآمد نیست: وام، پس‌گرفتن قرض، و برگشت پول هم واریز می‌شوند.
# is_income = NULL یعنی هنوز تصمیم نگرفته و در هیچ‌کدام شمرده نمی‌شود.
_IN = case(
    (
        and_(Transaction.is_income.is_(True), Transaction.amount_rial > 0),
        Transaction.amount_rial,
    ),
    else_=0,
)

# واریزی‌های بلاتکلیف — تا وقتی تصمیم نگیرد، جایی شمرده نمی‌شوند
_PENDING_IN = case(
    (
        and_(Transaction.is_income.is_(None), Transaction.amount_rial > 0),
        Transaction.amount_rial,
    ),
    else_=0,
)

# «واقعی» یعنی نه انتقال بین حساب‌های خودم، نه حواله‌ای که برگشت خورده.
# هر دو پول را جابه‌جا می‌کنند بدون آنکه خرج یا درآمد باشند.
_REAL = and_(Transaction.is_self_transfer.is_(False), Transaction.is_reversed.is_(False))


def get_setting(db: Session, key: str, default: str) -> str:
    row = db.get(AppSetting, key)
    return row.value if row else default


def _period_filters(stmt, start: date | None, end: date | None):
    if start:
        stmt = stmt.where(Transaction.occurred_date >= start)
    if end:
        stmt = stmt.where(Transaction.occurred_date < end)
    return stmt


# ---------------------------------------------------------------- خلاصه
def monthly_series(db: Session, months: int = 12) -> list[dict]:
    """درآمد/هزینه/خالص هر ماه جلالی."""
    rows = db.execute(
        select(
            Transaction.jalali_year,
            Transaction.jalali_month,
            func.coalesce(func.sum(_IN), 0),
            func.coalesce(func.sum(_OUT), 0),
            func.count(),
        )
        .where(_REAL)
        .group_by(Transaction.jalali_year, Transaction.jalali_month)
        .order_by(Transaction.jalali_year, Transaction.jalali_month)
    ).all()

    series = [
        {
            "year": y,
            "month": m,
            "label": month_label(y, m),
            "income_rial": int(i),
            "expense_rial": int(o),
            "net_rial": int(i) - int(o),
            "count": c,
        }
        for y, m, i, o, c in rows
    ]
    return series[-months:]


def summary(db: Session, year: int | None = None, month: int | None = None) -> dict:
    """خلاصهٔ یک ماه جلالی (پیش‌فرض: ماه جاری) در کنار جمع کل."""
    if year is None or month is None:
        year, month, _ = today_jalali_parts()

    row = db.execute(
        select(
            func.coalesce(func.sum(_IN), 0),
            func.coalesce(func.sum(_OUT), 0),
            func.count(),
        ).where(_REAL, Transaction.jalali_year == year, Transaction.jalali_month == month)
    ).one()

    overall = db.execute(
        select(
            func.coalesce(func.sum(_IN), 0),
            func.coalesce(func.sum(_OUT), 0),
            func.count(),
        ).where(_REAL)
    ).one()

    self_out = db.scalar(
        select(func.coalesce(func.sum(_OUT), 0)).where(
            Transaction.is_self_transfer.is_(True)
        )
    )
    pending = db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.needs_review.is_(True), _REAL)
    )
    latest = db.scalar(select(func.max(Transaction.jalali_datetime)))

    # واریزی‌هایی که هنوز تصمیم نگرفته درآمد هستند یا نه
    pending_income = db.execute(
        select(func.coalesce(func.sum(_PENDING_IN), 0), func.count()).where(
            _REAL, Transaction.is_income.is_(None), Transaction.amount_rial > 0
        )
    ).one()

    return {
        "year": year,
        "month": month,
        "label": month_label(year, month),
        "month_income_rial": int(row[0]),
        "month_expense_rial": int(row[1]),
        "month_net_rial": int(row[0]) - int(row[1]),
        "month_count": row[2],
        "total_income_rial": int(overall[0]),
        "total_expense_rial": int(overall[1]),
        "total_count": overall[2],
        "self_transfer_out_rial": int(self_out or 0),
        "pending_review": pending or 0,
        "latest_transaction": latest,
        "pending_income_rial": int(pending_income[0]),
        "pending_income_count": pending_income[1],
    }


# ---------------------------------------------------------------- تفکیک
def by_category(
    db: Session, start: date | None = None, end: date | None = None, direction: str = "out"
) -> list[dict]:
    amount = _OUT if direction == "out" else _IN
    stmt = (
        select(
            Category.id,
            Category.name_fa,
            Category.color,
            Category.parent_id,
            func.coalesce(func.sum(amount), 0),
            func.count(),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(_REAL)
        .group_by(Category.id, Category.name_fa, Category.color, Category.parent_id)
        .order_by(func.coalesce(func.sum(amount), 0).desc())
    )
    rows = db.execute(_period_filters(stmt, start, end)).all()
    return [
        {
            "category_id": cid,
            "name": name or "بدون دسته",
            "color": color or "#9ca3af",
            "parent_id": parent,
            "total_rial": int(total),
            "count": count,
        }
        for cid, name, color, parent, total, count in rows
        if int(total) > 0
    ]


def top_contacts(
    db: Session, start: date | None = None, end: date | None = None, limit: int = 15
) -> list[dict]:
    stmt = (
        select(
            Contact.id,
            Contact.name_fa,
            func.coalesce(func.sum(_OUT), 0),
            func.count(),
        )
        .join(Contact, Contact.id == Transaction.contact_id)
        .where(_REAL)
        .group_by(Contact.id, Contact.name_fa)
        .order_by(func.coalesce(func.sum(_OUT), 0).desc())
        .limit(limit)
    )
    rows = db.execute(_period_filters(stmt, start, end)).all()
    return [
        {"contact_id": mid, "name": name, "total_rial": int(total), "count": count}
        for mid, name, total, count in rows
        if int(total) > 0
    ]


def by_counterparty(
    db: Session, start: date | None = None, end: date | None = None, limit: int = 15
) -> list[dict]:
    """
    پرداخت به اشخاص، بر اساس نام نرمال‌شده.

    نرمال‌سازی اینجا حیاتی است: در فایل واقعی یک نفر با دو کدگذاری متفاوت
    نوشته شده بود و بدون آن، دو ردیف جدا با نصف مبلغ دیده می‌شد.
    """
    stmt = (
        select(
            Transaction.counterparty_name_norm,
            func.max(Transaction.counterparty_name),
            func.coalesce(func.sum(_OUT), 0),
            func.count(),
        )
        .where(_REAL, Transaction.counterparty_name_norm.is_not(None))
        .group_by(Transaction.counterparty_name_norm)
        .order_by(func.coalesce(func.sum(_OUT), 0).desc())
        .limit(limit)
    )
    rows = db.execute(_period_filters(stmt, start, end)).all()
    return [
        {"name": display, "name_norm": norm, "total_rial": int(total), "count": count}
        for norm, display, total, count in rows
        if int(total) > 0
    ]


# ---------------------------------------------------------------- هدررفت
def micro_spend(db: Session, months: int = 12) -> dict:
    """
    خردخرجی: تراکنش‌های کوچکی که جدا‌جدا ناچیزند ولی جمعشان بزرگ است.
    (در نمونهٔ واقعی ۱۷۸ کارمزد و ۷۳ شارژ سیم‌کارت در همین گروه بودند.)
    """
    threshold = int(get_setting(db, "micro_spend_threshold_rial", "1000000"))
    rows = db.execute(
        select(
            Category.name_fa,
            Category.color,
            func.count(),
            func.coalesce(func.sum(_OUT), 0),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(_REAL, Transaction.direction == "out", _OUT > 0, _OUT <= threshold)
        .group_by(Category.name_fa, Category.color)
        .order_by(func.coalesce(func.sum(_OUT), 0).desc())
    ).all()

    total = sum(int(r[3]) for r in rows)
    count = sum(r[2] for r in rows)
    all_out = db.scalar(
        select(func.coalesce(func.sum(_OUT), 0)).where(_REAL, Transaction.direction == "out")
    )
    return {
        "threshold_rial": threshold,
        "count": count,
        "total_rial": total,
        "share_of_expense": (total / int(all_out)) if all_out else 0.0,
        "by_category": [
            {"name": n or "بدون دسته", "color": c or "#9ca3af", "count": k, "total_rial": int(t)}
            for n, c, k, t in rows
        ],
    }


def month_over_month(db: Session, lookback: int = 3) -> dict:
    """
    جهش‌های ماه‌به‌ماه: دسته‌هایی که ماه گذشته نسبت به میانگین چند ماه
    قبلش به‌طور معنادار بالا رفته‌اند.
    """
    factor = float(get_setting(db, "mom_alert_factor", "1.5"))
    rows = db.execute(
        select(
            Transaction.jalali_year,
            Transaction.jalali_month,
            Category.id,
            Category.name_fa,
            Category.color,
            func.coalesce(func.sum(_OUT), 0),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(_REAL)
        .group_by(
            Transaction.jalali_year,
            Transaction.jalali_month,
            Category.id,
            Category.name_fa,
            Category.color,
        )
    ).all()

    by_cat: dict[int | None, dict[tuple[int, int], int]] = defaultdict(dict)
    names: dict[int | None, tuple[str, str]] = {}
    periods: set[tuple[int, int]] = set()
    for y, m, cid, name, color, total in rows:
        if int(total) <= 0:
            continue
        by_cat[cid][(y, m)] = int(total)
        names[cid] = (name or "بدون دسته", color or "#9ca3af")
        periods.add((y, m))

    if not periods:
        return {"current_period": None, "lookback_months": 0, "factor": factor, "categories": []}

    ordered = sorted(periods)
    current = ordered[-1]
    previous = ordered[-1 - lookback : -1]

    out = []
    for cid, series in by_cat.items():
        now = series.get(current, 0)
        history = [series.get(p, 0) for p in previous]
        baseline = statistics.mean(history) if history else 0
        name, color = names[cid]
        out.append(
            {
                "category_id": cid,
                "name": name,
                "color": color,
                "current_rial": now,
                "baseline_rial": int(baseline),
                "ratio": (now / baseline) if baseline else None,
                "is_spike": bool(baseline and now > baseline * factor),
                "delta_rial": now - int(baseline),
            }
        )

    out.sort(key=lambda r: r["delta_rial"], reverse=True)
    return {
        "current_period": {"year": current[0], "month": current[1], "label": month_label(*current)},
        "lookback_months": len(previous),
        "factor": factor,
        "categories": out,
    }


_DIGITS_RE = re.compile(r"\d+")


def _signature(tx: Transaction) -> tuple[str, str]:
    """کلید گروه‌بندی برای تشخیص تکرارشونده، به‌ترتیب دقت."""
    if tx.contact_id:
        return ("contact", str(tx.contact_id))
    if tx.terminal_id:
        return (tx.terminal_kind or "terminal", tx.terminal_id)
    if tx.phone_number:
        return ("phone", tx.phone_number)
    if tx.biller_id:
        return ("biller_id", tx.biller_id)
    if tx.counterparty_card:
        return ("card", tx.counterparty_card)
    if tx.deposit_no:
        return ("deposit_no", tx.deposit_no)
    # آخرین راه: متن شرح بدون عدد — «بستهٔ اینترنتی ایرانسل …» با هم جمع می‌شود
    return ("text", _DIGITS_RE.sub("#", tx.description_norm or "")[:120])


_PATTERNS = [
    ("هفتگی", 6, 8, 52),
    ("دوهفته‌ای", 12, 16, 26),
    ("ماهانه", 25, 36, 12),
    ("دوماهه", 55, 66, 6),
    ("فصلی", 85, 96, 4),
    ("سالانه", 350, 380, 1),
]


# دسته‌هایی که خرج تکرارشونده‌اند ولی «هدررفت» نیستند.
# قسط وام و اجاره را نمی‌شود قطع کرد؛ گذاشتنشان کنار اشتراک‌ها، عدد
# هدررفت را متورم و بی‌معنا می‌کند.
COMMITMENT_KINDS = {CategoryKind.LOAN}
COMMITMENT_SLUGS = {"loan_installment", "rent", "housing", "building_charge"}


def _is_commitment(tx: Transaction) -> bool:
    cat = tx.category
    if cat is None:
        return False
    return cat.kind in COMMITMENT_KINDS or cat.slug in COMMITMENT_SLUGS


def recurring(db: Session, min_occurrences: int = 3) -> list[dict]:
    """
    کشف خرج‌های تکرارشونده.

    هر گروه با `is_commitment` برمی‌گردد: اقساط وام و اجاره تعهد ثابت‌اند
    (باید دیده شوند ولی هدررفت نیستند)، بقیه اشتراک و خرج قابل‌قطع.
    """
    txns = list(
        db.scalars(
            select(Transaction)
            .where(_REAL, Transaction.direction == "out")
            .order_by(Transaction.occurred_date)
        )
    )

    groups: dict[tuple[str, str], list[Transaction]] = defaultdict(list)
    for tx in txns:
        groups[_signature(tx)].append(tx)

    out = []
    for (kind, value), items in groups.items():
        if len(items) < min_occurrences:
            continue
        dates = sorted(t.occurred_date for t in items)
        gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
        if not gaps:
            continue

        median_gap = statistics.median(gaps)
        amounts = [abs(t.amount_rial) for t in items]
        mean_amount = statistics.mean(amounts)
        cv = (statistics.pstdev(amounts) / mean_amount) if mean_amount else 1.0

        label, per_year = None, None
        for name, low, high, freq in _PATTERNS:
            if low <= median_gap <= high:
                label, per_year = name, freq
                break
        if label is None:
            continue
        # مبلغ باید نسبتاً پایدار باشد وگرنه صرفاً «جای پرتکرار» است نه اشتراک
        if cv > 0.35:
            continue

        sample = items[-1]
        out.append(
            {
                "key_kind": kind,
                "key_value": value,
                "name": sample.contact.name_fa
                if sample.contact
                else (sample.counterparty_name or sample.bank_tx_type or "نامشخص"),
                "category_name": sample.category.name_fa if sample.category else None,
                "occurrences": len(items),
                "median_gap_days": int(median_gap),
                "cadence": label,
                "avg_amount_rial": int(mean_amount),
                "last_amount_rial": abs(sample.amount_rial),
                "total_paid_rial": sum(amounts),
                "estimated_annual_rial": int(mean_amount * per_year),
                "first_seen": to_jalali_str(dates[0]),
                "last_seen": to_jalali_str(dates[-1]),
                "sample_description": sample.description_raw[:160],
                "amount_stability": round(1 - cv, 2),
                "is_commitment": _is_commitment(sample),
            }
        )

    out.sort(key=lambda r: r["estimated_annual_rial"], reverse=True)
    return out


# ---------------------------------------------------------------- بودجه
def budget_status(db: Session, year: int | None = None, month: int | None = None) -> list[dict]:
    if year is None or month is None:
        year, month, _ = today_jalali_parts()

    budgets = list(db.scalars(select(Budget)))
    # بودجهٔ همان ماه بر بودجهٔ پیش‌فرض اولویت دارد
    chosen: dict[int, Budget] = {}
    for b in budgets:
        if b.jalali_year is None and b.jalali_month is None:
            chosen.setdefault(b.category_id, b)
    for b in budgets:
        if b.jalali_year == year and b.jalali_month == month:
            chosen[b.category_id] = b

    if not chosen:
        return []

    spent_rows = db.execute(
        select(Transaction.category_id, func.coalesce(func.sum(_OUT), 0))
        .where(_REAL, Transaction.jalali_year == year, Transaction.jalali_month == month)
        .group_by(Transaction.category_id)
    ).all()
    spent = {cid: int(total) for cid, total in spent_rows}

    out = []
    for cat_id, budget in chosen.items():
        category = db.get(Category, cat_id)
        used = spent.get(cat_id, 0)
        out.append(
            {
                "budget_id": budget.id,
                "category_id": cat_id,
                "category_name": category.name_fa if category else "—",
                "color": category.color if category else "#64748b",
                "amount_rial": budget.amount_rial,
                "spent_rial": used,
                "remaining_rial": budget.amount_rial - used,
                "ratio": (used / budget.amount_rial) if budget.amount_rial else 0,
                "is_over": used > budget.amount_rial,
                "scope": "ماه جاری" if budget.jalali_month else "پیش‌فرض",
            }
        )
    out.sort(key=lambda r: r["ratio"], reverse=True)
    return out
