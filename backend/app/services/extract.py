"""
استخراج موجودیت از «شرح سند».

فایل بانک نام فروشگاه را نمی‌دهد؛ فقط شمارهٔ پایانه. این شناسه‌ها تنها راه
تشخیص «این خرید از کجا بود» هستند و پایهٔ برچسب‌زدنِ یک‌باره‌اند.
همهٔ الگوها روی نمونهٔ واقعیِ ۱۲۱۵ تراکنشیِ بانک سامان آزموده شده‌اند.
"""

import re
from dataclasses import dataclass, field

from app.services.normalize import digits_only, fa_digits, fold_name, normalize

_RE_POS_TERMINAL = re.compile(r"پایانه\s*فروش\s*[:：]?\s*(\d{6,12})")
_RE_NET_TERMINAL = re.compile(r"از\s*اینترنت\s*[:：]?\s*(\d{6,12})")
_RE_CARD = re.compile(r"کارت\s*شماره\s*[:：]?\s*(\d{16})")
_RE_IBAN = re.compile(r"\b(IR\d{24})\b", re.IGNORECASE)
_RE_DEPOSIT = re.compile(r"شماره\s*سپرده\s*[:：]?\s*(\d{6,24})")
_RE_PHONE = re.compile(r"شماره\s*تلفن\s*[:：]?\s*(0\d{9,10})")
_RE_LOAN = re.compile(r"\b(LN[_\-]?\d+)\b", re.IGNORECASE)
_RE_BILLER = re.compile(r"پرداخت\s*قبض\s*از\s*[:：]?\s*(\d{6,20})")
_RE_TRACE = re.compile(r"ش\s*م\s*[:：]?\s*(\d{6,20})")
_RE_BANK = re.compile(r"بانک\s+([آ-یA-Za-z]+(?:\s+[آ-یA-Za-z]+)?)")
# واژه‌هایی که اگر بعد از نام بانک بیایند جزو نام نیستند («بانک پاسارگاد بنام: …»)
_BANK_STOP = {"بنام", "شماره", "کد", "ش", "به", "از", "بابت"}

# نام طرف‌حساب: «بنام: X از درگاه…» / «بنام X - کد پیگیری…» / «بنام: X»
_RE_PARTY = re.compile(
    r"بنام\s*[:：]?\s*(.+?)\s*(?:از\s*درگاه|[-–—]\s*(?:شماره|کد|ش\s)|\s[-–—]\s|$)"
)

# عبارت‌هایی که اگر داخل نام افتادند باید بریده شوند
_PARTY_TAIL = re.compile(r"\s*(?:بانک\s+\S+.*|شماره\s+.*|کد\s+.*)$")


@dataclass
class Extracted:
    counterparty_name: str | None = None
    counterparty_name_norm: str | None = None
    counterparty_iban: str | None = None
    counterparty_card: str | None = None
    counterparty_bank: str | None = None
    terminal_id: str | None = None
    terminal_kind: str | None = None
    deposit_no: str | None = None
    phone_number: str | None = None
    biller_id: str | None = None
    loan_ref: str | None = None
    trace_ref: str | None = None

    def identifier_pairs(self) -> list[tuple[str, str]]:
        """
        شناسه‌های این تراکنش به‌ترتیب اعتماد — برای تطبیق با فروشنده.
        شمارهٔ پایانه دقیق‌ترین است؛ نام آخرین گزینه است چون تکراری می‌شود.
        """
        pairs: list[tuple[str, str]] = []
        if self.terminal_id and self.terminal_kind:
            pairs.append((self.terminal_kind, self.terminal_id))
        if self.counterparty_card:
            pairs.append(("card", self.counterparty_card))
        if self.counterparty_iban:
            pairs.append(("iban", self.counterparty_iban))
        if self.deposit_no:
            pairs.append(("deposit_no", self.deposit_no))
        if self.phone_number:
            pairs.append(("phone", self.phone_number))
        if self.biller_id:
            pairs.append(("biller_id", self.biller_id))
        return pairs


def _first(pattern: re.Pattern, text: str) -> str | None:
    m = pattern.search(text)
    return m.group(1) if m else None


def extract(description: str) -> Extracted:
    """شرح سند خام → موجودیت‌های ساختاریافته."""
    text = normalize(description)
    out = Extracted()

    if pos := _first(_RE_POS_TERMINAL, text):
        out.terminal_id, out.terminal_kind = pos, "pos_terminal"
    elif net := _first(_RE_NET_TERMINAL, text):
        out.terminal_id, out.terminal_kind = net, "internet_terminal"

    out.counterparty_card = _first(_RE_CARD, text)
    if iban := _first(_RE_IBAN, text):
        out.counterparty_iban = iban.upper()
    out.deposit_no = _first(_RE_DEPOSIT, text)
    out.phone_number = _first(_RE_PHONE, text)
    out.biller_id = _first(_RE_BILLER, text)
    out.trace_ref = _first(_RE_TRACE, text)

    if loan := _first(_RE_LOAN, text):
        out.loan_ref = loan.upper().replace("-", "_")
    if bank := _first(_RE_BANK, text):
        words = [w for w in bank.split() if w not in _BANK_STOP]
        out.counterparty_bank = " ".join(words) or None

    if m := _RE_PARTY.search(text):
        name = _PARTY_TAIL.sub("", m.group(1)).strip(" .،-–—:")
        # نام‌های تک‌حرفی یا صرفاً عددی، نام نیستند
        if len(name) >= 3 and not name.isdigit():
            out.counterparty_name = name
            out.counterparty_name_norm = fold_name(name)

    return out


def clean_amount(value) -> int:
    """
    مقدار سلول اکسل → ریالِ صحیح.

    اعداد بزرگ در فایل به‌شکل نمایی می‌آیند («1.1E8») و باید بدون خطای اعشار
    به عدد صحیح تبدیل شوند.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, (int,)):
        return int(value)
    if isinstance(value, float):
        return int(round(value))
    # رشته: اول به‌صورت عدد (شامل نمایی مثل «1.1E8») تفسیر می‌شود،
    # و فقط اگر نشد، رقم‌ها جدا می‌شوند (برای «۱٬۱۰۰٬۰۰۰ ریال»).
    text = fa_digits(str(value)).replace(",", "").replace("٬", "").strip()
    try:
        return int(round(float(text)))
    except ValueError:
        digits = digits_only(text)
        return int(digits) if digits else 0
