from enum import StrEnum


class Bank(StrEnum):
    SAMAN = "saman"
    BLU = "blu"
    MELLI = "melli"
    MEHR = "mehr"
    OTHER = "other"


BANK_LABELS_FA = {
    Bank.SAMAN: "بانک سامان",
    Bank.BLU: "بلو بانک",
    Bank.MELLI: "بانک ملی",
    Bank.MEHR: "بانک مهر ایران",
    Bank.OTHER: "سایر",
}


class Direction(StrEnum):
    IN = "in"
    OUT = "out"


class CategoryKind(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    FEE = "fee"
    LOAN = "loan"
    ADJUSTMENT = "adjustment"


class IdentifierKind(StrEnum):
    """انواع شناسه‌ای که می‌توان یک فروشنده/شخص را با آن تشخیص داد."""

    POS_TERMINAL = "pos_terminal"
    INTERNET_TERMINAL = "internet_terminal"
    CARD = "card"
    IBAN = "iban"
    DEPOSIT_NO = "deposit_no"
    PHONE = "phone"
    BILLER_ID = "biller_id"


IDENTIFIER_LABELS_FA = {
    IdentifierKind.POS_TERMINAL: "پایانه فروش",
    IdentifierKind.INTERNET_TERMINAL: "درگاه اینترنتی",
    IdentifierKind.CARD: "شماره کارت",
    IdentifierKind.IBAN: "شماره شبا",
    IdentifierKind.DEPOSIT_NO: "شماره سپرده",
    IdentifierKind.PHONE: "شماره تلفن",
    IdentifierKind.BILLER_ID: "شناسه قبض",
}


class ContactKind(StrEnum):
    PERSON = "person"
    BUSINESS = "business"
    OWN = "own"


CONTACT_KIND_LABELS_FA = {
    ContactKind.PERSON: "شخص",
    ContactKind.BUSINESS: "کسب‌وکار",
    ContactKind.OWN: "حساب خودم",
}


class DebtDirection(StrEnum):
    """جهت قرض — از دید کاربر."""

    I_LENT = "i_lent"        # به کسی قرض دادم → طلبکارم
    I_BORROWED = "i_borrowed"  # از کسی قرض گرفتم → بدهکارم


DEBT_DIRECTION_LABELS_FA = {
    DebtDirection.I_LENT: "قرض دادم",
    DebtDirection.I_BORROWED: "قرض گرفتم",
}


class DebtEntryKind(StrEnum):
    PRINCIPAL = "principal"    # اصل مبلغ رد و بدل شد
    REPAYMENT = "repayment"    # بازپرداخت


class DebtStatus(StrEnum):
    OPEN = "open"
    SETTLED = "settled"


class CategorizedBy(StrEnum):
    MANUAL = "manual"
    CONTACT = "contact"
    RULE = "rule"
    SYSTEM = "system"
    NONE = "none"


class ImportStatus(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"
    FAILED = "failed"


class InstallmentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"


class LoanStatus(StrEnum):
    ACTIVE = "active"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class WishPriority(StrEnum):
    NEED = "need"      # ضروری
    NICE = "nice"      # خوب است باشد
    SOMEDAY = "someday"  # روزی روزگاری


WISH_PRIORITY_LABELS_FA = {
    WishPriority.NEED: "ضروری",
    WishPriority.NICE: "خوب است باشد",
    WishPriority.SOMEDAY: "روزی روزگاری",
}

WISH_PRIORITY_ORDER = {
    WishPriority.NEED: 0,
    WishPriority.NICE: 1,
    WishPriority.SOMEDAY: 2,
}
