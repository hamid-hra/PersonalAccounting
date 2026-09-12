"""
کشف پیوند بین تراکنش‌ها.

سه الگو که اگر پیدا نشوند، آمار جدی گمراه‌کننده می‌شود:

۱. **انتقال بین حساب‌های خودم** — یک جابه‌جایی که در هر دو صورتحساب هست.
   روی دادهٔ واقعی: انتقال پل از ملی به سامان، فاصلهٔ ۴ ثانیه، مبلغ یکسان.
   اگر جفت نشود، هم «هزینه» شمرده می‌شود هم «درآمد».

۲. **حوالهٔ برگشتی** — ساتنا/پایای ناموفق که همان روز برمی‌گردد.
   روی دادهٔ واقعی حدود ۷۰۰ میلیون تومان درآمد و هزینهٔ خیالی می‌ساخت.

۳. **کارمزد** — سطر جدایی که متعلق به یک تراکنش دیگر است.
"""

import re
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Transaction, TxLink
from app.services.normalize import fold

# پنجرهٔ زمانی هر نوع تطبیق
CROSS_ACCOUNT_WINDOW = timedelta(minutes=5)
REVERSAL_WINDOW = timedelta(days=7)
FEE_WINDOW = timedelta(minutes=5)

# واژه‌هایی که یک تراکنش را «برگشتی» می‌کنند
_REVERSAL_WORDS = ("برگشت", "عودت", "اصلاح سند", "استرداد")
_FEE_WORDS = ("کارمزد",)

# دنبالهٔ عددیِ مشترک در شمارهٔ پیگیری کارمزد و تراکنش اصلی
# (بانک ملی: BCG11264 و Z_G11264)
_DIGITS = re.compile(r"\d{4,}")


def _is_reversal_text(tx: Transaction) -> bool:
    blob = f"{tx.bank_tx_type or ''} {tx.description_norm or ''}"
    return any(word in blob for word in _REVERSAL_WORDS)


def _is_fee(tx: Transaction) -> bool:
    return any(word in (tx.bank_tx_type or "") for word in _FEE_WORDS)


def _account_refs(tx: Transaction) -> set[str]:
    """شناسه‌هایی که تراکنش به حساب مقصد نسبت می‌دهد."""
    out = set()
    for value in (tx.counterparty_iban, tx.deposit_no, tx.counterparty_card):
        if value:
            out.add(fold(value))
    return out


def _account_identity(account: Account) -> set[str]:
    out = set()
    for value in (account.iban, account.account_number):
        if value:
            out.add(fold(value))
            out.add(fold(value.lstrip("0")))
    return out


def _shared_reference(a: Transaction, b: Transaction) -> bool:
    """آیا شمارهٔ پیگیری یا سند مشترکی دارند؟ قوی‌ترین شاهدِ ارتباط است."""
    keys_a = set(_DIGITS.findall(f"{a.doc_number or ''} {a.trace_ref or ''}"))
    keys_b = set(_DIGITS.findall(f"{b.doc_number or ''} {b.trace_ref or ''}"))
    return bool(keys_a & keys_b)


def _reversal_confidence(out_tx: Transaction, in_tx: Transaction, gap) -> tuple[float, str]:
    """
    چقدر مطمئنیم این واقعاً برگشتِ همان تراکنش است؟

    فاصلهٔ زیاد بین دو مبلغِ گردِ کوچک شاهد نیست، حدس است — چنین جفتی با
    اطمینان پایین ساخته می‌شود تا خودکار اعمال نشود و کاربر تأییدش کند.
    """
    hours = gap.total_seconds() / 3600
    if _shared_reference(out_tx, in_tx):
        return 0.98, "شمارهٔ پیگیری مشترک"
    if hours <= 1:
        return 0.9, f"همان حساب، مبلغ برابر، «{in_tx.bank_tx_type}»"
    if hours <= 6:
        return 0.75, f"همان روز، مبلغ برابر، «{in_tx.bank_tx_type}»"
    return 0.4, f"فقط مبلغ برابر با فاصلهٔ {hours:.0f} ساعت — نیازمند تأیید"


def _existing_pairs(db: Session) -> set[tuple[str, int, int]]:
    return {
        (link.kind, link.primary_tx_id, link.secondary_tx_id)
        for link in db.scalars(select(TxLink))
    }


def detect_links(db: Session) -> dict[str, int]:
    """
    همهٔ الگوها را روی کل تراکنش‌ها اجرا می‌کند و پیوندهای تازه را می‌سازد.
    idempotent است — اجرای دوباره پیوند تکراری نمی‌سازد.
    """
    accounts = {a.id: a for a in db.scalars(select(Account))}
    identity = {aid: _account_identity(a) for aid, a in accounts.items()}
    txns = list(db.scalars(select(Transaction).order_by(Transaction.occurred_at)))
    seen = _existing_pairs(db)
    linked: set[int] = set()
    created = {"cross_account": 0, "reversal": 0, "fee": 0}

    # ایندکس بر اساس مبلغ مطلق، تا مقایسه از O(n²) در نیاید
    by_amount: dict[int, list[Transaction]] = defaultdict(list)
    for tx in txns:
        by_amount[abs(tx.amount_rial)].append(tx)

    def add(kind: str, primary: Transaction, secondary: Transaction, conf: float, why: str):
        key = (kind, primary.id, secondary.id)
        if key in seen:
            return False
        seen.add(key)
        db.add(
            TxLink(
                kind=kind,
                primary_tx_id=primary.id,
                secondary_tx_id=secondary.id,
                # برای کارمزد، مبلغِ خودِ کارمزد معنا دارد نه تراکنش اصلی
                amount_rial=abs(secondary.amount_rial if kind == "fee" else primary.amount_rial),
                seconds_apart=int(
                    abs((primary.occurred_at - secondary.occurred_at).total_seconds())
                ),
                confidence=conf,
                matched_by=why,
            )
        )
        created[kind] += 1
        return True

    # ---------------- ۱ و ۲: جفت‌های مبلغ‌برابرِ مخالف‌جهت ----------------
    for amount, group in by_amount.items():
        if amount == 0 or len(group) < 2:
            continue
        outs = [t for t in group if t.amount_rial < 0]
        ins = [t for t in group if t.amount_rial > 0]
        for out_tx in outs:
            if out_tx.id in linked:
                continue
            # نزدیک‌ترین نامزد از نظر زمان، نه اولین نامزد. مبلغ‌های گرد و
            # کوچک (کارمزد ۵۰۰ تومانی) بارها تکرار می‌شوند و انتخاب دلبخواهی
            # جفت‌های بی‌ربط می‌سازد.
            candidates = sorted(
                (t for t in ins if t.id not in linked),
                key=lambda t: abs(t.occurred_at - out_tx.occurred_at),
            )
            for in_tx in candidates:
                gap = abs(out_tx.occurred_at - in_tx.occurred_at)

                # ---- برگشتی: همان حساب، متن برگشت ----
                if out_tx.account_id == in_tx.account_id:
                    if gap > REVERSAL_WINDOW or not _is_reversal_text(in_tx):
                        continue
                    conf, why = _reversal_confidence(out_tx, in_tx, gap)
                    if add("reversal", out_tx, in_tx, conf, why):
                        linked.update({out_tx.id, in_tx.id})
                        break
                    continue

                # ---- انتقال بین حساب‌های خودم ----
                if gap > CROSS_ACCOUNT_WINDOW:
                    continue
                out_refs = _account_refs(out_tx)
                in_refs = _account_refs(in_tx)
                points_to_target = bool(out_refs & identity.get(in_tx.account_id, set()))
                points_to_source = bool(in_refs & identity.get(out_tx.account_id, set()))
                if points_to_target or points_to_source:
                    why = "شبا/شماره حساب دو طرف با هم می‌خواند"
                    conf = 1.0 if (points_to_target and points_to_source) else 0.9
                elif out_tx.is_self_transfer and in_tx.is_self_transfer:
                    why = "هر دو انتقال داخلی، مبلغ و زمان یکسان"
                    conf = 0.7
                else:
                    continue
                if add("cross_account", out_tx, in_tx, conf, why):
                    linked.update({out_tx.id, in_tx.id})
                    break

    # ---------------- ۳: کارمزد → تراکنش اصلی ----------------
    by_account: dict[int, list[Transaction]] = defaultdict(list)
    for tx in txns:
        by_account[tx.account_id].append(tx)

    for account_txns in by_account.values():
        fees = [t for t in account_txns if _is_fee(t)]
        others = [t for t in account_txns if not _is_fee(t)]
        for fee in fees:
            fee_keys = set(_DIGITS.findall(f"{fee.doc_number or ''} {fee.trace_ref or ''}"))
            best = None
            for parent in others:
                if abs(parent.occurred_at - fee.occurred_at) > FEE_WINDOW:
                    continue
                parent_keys = set(
                    _DIGITS.findall(f"{parent.doc_number or ''} {parent.trace_ref or ''}")
                )
                if fee_keys & parent_keys:
                    best = parent
                    break
            if best is not None:
                add("fee", best, fee, 0.9, "شمارهٔ پیگیری مشترک")

    db.commit()
    apply_links(db)
    return created


def apply_links(db: Session) -> int:
    """
    اثر پیوندهای تأییدشده (یا با اطمینان بالا) را روی تراکنش‌ها می‌نشاند.

    برگشتی‌ها `is_reversed` می‌شوند و انتقال‌های بین‌حسابی `is_self_transfer`،
    تا از درآمد و هزینه بیرون بمانند.
    """
    changed = 0
    # اول همه را پاک می‌کنیم تا پیوندِ ردشده اثرش برداشته شود
    for tx in db.scalars(select(Transaction).where(Transaction.is_reversed.is_(True))):
        tx.is_reversed = False
        changed += 1

    links = db.scalars(select(TxLink).where(TxLink.is_rejected.is_(False)))
    for link in links:
        if link.confidence < 0.7 and not link.is_confirmed:
            continue
        primary = db.get(Transaction, link.primary_tx_id)
        secondary = db.get(Transaction, link.secondary_tx_id)
        if primary is None or secondary is None:
            continue

        if link.kind == "reversal":
            primary.is_reversed = True
            secondary.is_reversed = True
            changed += 2
        elif link.kind == "cross_account":
            for tx in (primary, secondary):
                if not tx.is_self_transfer:
                    tx.is_self_transfer = True
                    tx.is_transfer = True
                    tx.needs_review = False
                    changed += 1

    db.commit()
    return changed


def link_summary(db: Session) -> dict:
    """آمار پیوندها برای داشبورد و صفحهٔ بررسی."""
    out: dict[str, dict] = {}
    for kind in ("cross_account", "reversal", "fee"):
        rows = list(
            db.scalars(select(TxLink).where(TxLink.kind == kind, TxLink.is_rejected.is_(False)))
        )
        out[kind] = {
            "count": len(rows),
            "total_rial": sum(r.amount_rial for r in rows),
            "confirmed": sum(1 for r in rows if r.is_confirmed),
        }
    return out
