"""
موتور دسته‌بندی.

ترتیب اولویت — از مطمئن‌ترین به کلی‌ترین:
  ۱. برچسب دستی کاربر (هرگز بازنویسی نمی‌شود)
  ۲. انتقال بین حساب‌های خودم → از تحلیل هزینه کنار گذاشته می‌شود
  ۳. شناسهٔ فروشنده (پایانه/کارت/شبا/سپرده/تلفن) ← اینجا «یادگیری» رخ می‌دهد
  ۴. قوانین کاربر
  ۵. قوانین سیستمی روی «نوع تراکنش» بانک
  ۶. بدون دسته + نیازمند بررسی
"""

import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.enums import CategorizedBy
from app.models import Category, Contact, ContactIdentifier, OwnerAlias, Rule, Transaction
from app.services.normalize import fold, fold_name, fold_name_key


class Categorizer:
    """
    وضعیت لازم برای دسته‌بندی را یک‌بار می‌خواند و روی هزاران تراکنش
    بدون کوئری اضافه اعمال می‌کند.
    """

    def __init__(self, db: Session):
        self.db = db
        self.categories: dict[str, Category] = {
            c.slug: c for c in db.scalars(select(Category))
        }

        aliases = list(db.scalars(select(OwnerAlias)))
        # نام‌ها با کلیدِ بی‌اعتنا به ترتیب کلمه نگه داشته می‌شوند، چون هر بانک
        # ترتیب متفاوتی می‌نویسد («علی رضایی» در سامان، «رضایی علی» در ملی).
        self.owner_names: set[str] = {
            fold_name_key(a.value) for a in aliases if a.kind == "name" and a.value
        }
        self.owner_ids: set[str] = {
            a.value_norm for a in aliases if a.kind != "name" and a.value_norm
        }

        self.identifiers: dict[tuple[str, str], ContactIdentifier] = {
            (i.kind, i.value): i for i in db.scalars(select(ContactIdentifier))
        }
        self.contacts: dict[int, Contact] = {m.id: m for m in db.scalars(select(Contact))}
        self.contacts_by_name: dict[str, Contact] = {
            key: c
            for c in self.contacts.values()
            if (key := fold_name_key(c.name_fa))
        }

        # قوانین کاربر قبل از قوانین سیستمی
        rules = list(db.scalars(select(Rule).where(Rule.is_active.is_(True))))
        self.rules = sorted(rules, key=lambda r: (r.is_system, r.priority, r.id))
        self._regex_cache: dict[str, re.Pattern] = {}

    # ------------------------------------------------------------------
    def _cat_id(self, slug: str) -> int | None:
        cat = self.categories.get(slug)
        return cat.id if cat else None

    def _regex(self, pattern: str) -> re.Pattern:
        if pattern not in self._regex_cache:
            self._regex_cache[pattern] = re.compile(pattern, re.IGNORECASE)
        return self._regex_cache[pattern]

    # ------------------------------------------------------------------
    def is_self_transfer(self, tx: Transaction) -> bool:
        """
        آیا طرف مقابل، خودِ کاربر است؟

        در نمونهٔ واقعی ۴۲٪ خروجی حساب همین بود؛ اگر جدا نشود همهٔ آمار
        هزینه چند برابر واقعیت نشان داده می‌شود.
        """
        if tx.is_self_declared:
            return True  # خود بانک صریحاً گفته «انتقال بين حساب هاي خود»
        if tx.counterparty_name and fold_name_key(tx.counterparty_name) in self.owner_names:
            return True
        for value in (tx.counterparty_card, tx.counterparty_iban, tx.deposit_no):
            if value and fold(value) in self.owner_ids:
                return True
        return False

    def match_contact(self, tx: Transaction) -> Contact | None:
        """
        تطبیق تراکنش با مخاطب — اول با شناسهٔ دقیق (پایانه/کارت/شبا/سپرده)،
        و اگر نشد با نامِ بی‌اعتنا به ترتیب کلمه.
        """
        for kind, value in _identifier_pairs(tx):
            ident = self.identifiers.get((kind, value))
            if ident:
                return self.contacts.get(ident.contact_id)
        if tx.counterparty_name:
            return self.contacts_by_name.get(fold_name_key(tx.counterparty_name))
        return None

    def match_rule(self, tx: Transaction) -> Rule | None:
        for rule in self.rules:
            if self._rule_matches(rule, tx):
                return rule
        return None

    def _rule_matches(self, rule: Rule, tx: Transaction) -> bool:
        if rule.match_bank_tx_type and fold(rule.match_bank_tx_type) != fold(tx.bank_tx_type):
            return False
        if rule.match_direction and rule.match_direction != tx.direction:
            return False
        amount = abs(tx.amount_rial)
        if rule.match_amount_min is not None and amount < rule.match_amount_min:
            return False
        if rule.match_amount_max is not None and amount > rule.match_amount_max:
            return False
        if rule.match_description_regex and not self._regex(rule.match_description_regex).search(
            tx.description_norm or ""
        ):
            return False
        if rule.match_counterparty_regex and not self._regex(
            rule.match_counterparty_regex
        ).search(tx.counterparty_name or ""):
            return False
        return True

    # ------------------------------------------------------------------
    def apply(self, tx: Transaction, *, force: bool = False) -> None:
        """
        دسته‌بندی یک تراکنش. برچسب دستی کاربر دست‌نخورده می‌ماند مگر force.
        """
        if tx.categorized_by == CategorizedBy.MANUAL and not force:
            return

        tx.is_self_transfer = False
        tx.is_transfer = False
        tx.contact_id = None

        # ۲ — انتقال بین حساب‌های خودم
        if self.is_self_transfer(tx):
            tx.is_self_transfer = True
            tx.is_transfer = True
            tx.is_income = False  # پول خودم که جابه‌جا شده، درآمد نیست
            tx.category_id = self._cat_id("self_transfer")
            tx.categorized_by = CategorizedBy.SYSTEM
            tx.needs_review = False
            return

        # ۳ — مخاطب شناخته‌شده. دسته بسته به جهت پول فرق می‌کند:
        # از «شرکت نمونه» پول بیاید حقوق است، به او پول بدهم چیز دیگر.
        contact = self.match_contact(tx)
        if contact is not None:
            tx.contact_id = contact.id
            category_id = contact.category_for(tx.direction)
            if category_id:
                tx.category_id = category_id
                tx.categorized_by = CategorizedBy.CONTACT
                tx.needs_review = False
                # اگر برای این مخاطب «دستهٔ دریافت» تعیین کرده‌ای، یعنی
                # پولی که از او می‌آید را قبلاً درآمد اعلام کرده‌ای — پس
                # واریزی‌های بعدی‌اش لازم نیست دوباره تأیید شوند.
                if tx.direction == "in" and contact.income_category_id:
                    tx.is_income = True
                return

        # ۴ و ۵ — قوانین
        rule = self.match_rule(tx)
        if rule is not None:
            if rule.set_category_id:
                tx.category_id = rule.set_category_id
            if rule.set_contact_id and tx.contact_id is None:
                tx.contact_id = rule.set_contact_id
            if rule.set_is_transfer is not None:
                tx.is_transfer = rule.set_is_transfer
            tx.needs_review = bool(rule.set_needs_review)
            tx.categorized_by = (
                CategorizedBy.SYSTEM if rule.is_system else CategorizedBy.RULE
            )
            # فروشنده شناخته شد ولی دستهٔ پیش‌فرض نداشت → دیگر نیاز به بررسی نیست
            if contact is not None:
                tx.needs_review = False
            return

        # ۶ — هیچ‌کدام
        tx.category_id = self._cat_id("uncategorized")
        tx.categorized_by = CategorizedBy.NONE
        tx.needs_review = True


def _identifier_pairs(tx: Transaction) -> list[tuple[str, str]]:
    """شناسه‌های تراکنش، به‌ترتیب دقت."""
    pairs: list[tuple[str, str]] = []
    if tx.terminal_id and tx.terminal_kind:
        pairs.append((tx.terminal_kind, tx.terminal_id))
    if tx.counterparty_card:
        pairs.append(("card", tx.counterparty_card))
    if tx.counterparty_iban:
        pairs.append(("iban", tx.counterparty_iban))
    if tx.deposit_no:
        pairs.append(("deposit_no", tx.deposit_no))
    if tx.phone_number:
        pairs.append(("phone", tx.phone_number))
    if tx.biller_id:
        pairs.append(("biller_id", tx.biller_id))
    return pairs


def recategorize_all(db: Session, *, force: bool = False) -> int:
    """
    اجرای دوبارهٔ کل خط لوله روی همهٔ تراکنش‌ها.

    بعد از هر تغییر در فروشنده‌ها، قوانین، یا فهرست «حساب‌های خودم» باید
    اجرا شود تا گذشته هم به‌روز شود.
    """
    cat = Categorizer(db)
    count = 0
    for tx in db.scalars(select(Transaction)):
        cat.apply(tx, force=force)
        count += 1
    db.commit()
    return count


def apply_contact_to_matching(db: Session, kind: str, value: str, contact: Contact) -> int:
    """
    برچسبِ تازه را روی همهٔ تراکنش‌های گذشتهٔ همان شناسه اعمال می‌کند.

    این همان کاری است که برچسب‌زدنِ یک پایانه را ارزشمند می‌کند: یک بار
    برچسب، و ۲۰۵ پایانهٔ ناشناس به‌تدریج معنا پیدا می‌کنند.
    """
    column = {
        "pos_terminal": Transaction.terminal_id,
        "internet_terminal": Transaction.terminal_id,
        "card": Transaction.counterparty_card,
        "iban": Transaction.counterparty_iban,
        "deposit_no": Transaction.deposit_no,
        "phone": Transaction.phone_number,
        "biller_id": Transaction.biller_id,
    }.get(kind)
    if column is None:
        return 0

    stmt = select(Transaction).where(column == value)
    if kind in {"pos_terminal", "internet_terminal"}:
        stmt = stmt.where(Transaction.terminal_kind == kind)

    changed = 0
    for tx in db.scalars(stmt):
        if tx.categorized_by == CategorizedBy.MANUAL:
            continue
        tx.contact_id = contact.id
        category_id = contact.category_for(tx.direction)
        if category_id:
            tx.category_id = category_id
            tx.categorized_by = CategorizedBy.CONTACT
        tx.needs_review = False
        changed += 1
    db.commit()
    return changed
