"""دسته‌ها و قوانین اولیه — بر پایهٔ ۱۹ «نوع تراکنش»ی که در صورتحساب واقعی دیده شد."""

from app.enums import CategoryKind as K

# (slug, نام، والد، نوع، رنگ، آیکن)
CATEGORIES: list[tuple[str, str, str | None, str, str, str]] = [
    # ---------- هزینه ----------
    ("food", "خوراک", None, K.EXPENSE, "#f97316", "utensils"),
    ("groceries", "سوپرمارکت و خواربار", "food", K.EXPENSE, "#fb923c", "shopping-basket"),
    ("restaurant", "رستوران و کافه", "food", K.EXPENSE, "#fdba74", "coffee"),
    ("transport", "حمل و نقل", None, K.EXPENSE, "#0ea5e9", "car"),
    ("taxi", "تاکسی و سفرهای درون‌شهری", "transport", K.EXPENSE, "#38bdf8", "car-taxi"),
    ("fuel", "سوخت", "transport", K.EXPENSE, "#7dd3fc", "fuel"),
    ("housing", "مسکن", None, K.EXPENSE, "#8b5cf6", "home"),
    ("rent", "اجاره", "housing", K.EXPENSE, "#a78bfa", "key"),
    ("building_charge", "شارژ ساختمان", "housing", K.EXPENSE, "#c4b5fd", "building"),
    ("utilities", "قبوض", None, K.EXPENSE, "#14b8a6", "receipt"),
    ("telecom", "اینترنت و ارتباطات", None, K.EXPENSE, "#06b6d4", "wifi"),
    ("net_package", "بستهٔ اینترنت", "telecom", K.EXPENSE, "#22d3ee", "globe"),
    ("sim_charge", "شارژ سیم‌کارت", "telecom", K.EXPENSE, "#67e8f9", "smartphone"),
    ("health", "سلامت و درمان", None, K.EXPENSE, "#ef4444", "heart-pulse"),
    ("clothing", "پوشاک", None, K.EXPENSE, "#ec4899", "shirt"),
    ("shopping", "خرید آنلاین", None, K.EXPENSE, "#d946ef", "shopping-cart"),
    ("entertainment", "سرگرمی و اشتراک‌ها", None, K.EXPENSE, "#f43f5e", "clapperboard"),
    ("education", "آموزش", None, K.EXPENSE, "#84cc16", "graduation-cap"),
    ("travel", "سفر", None, K.EXPENSE, "#eab308", "plane"),
    ("gift", "هدیه و کمک", None, K.EXPENSE, "#f472b6", "gift"),
    ("cash_withdraw", "برداشت نقدی", None, K.EXPENSE, "#94a3b8", "banknote"),
    ("other_expense", "سایر هزینه‌ها", None, K.EXPENSE, "#64748b", "circle-dashed"),
    ("uncategorized", "بدون دسته", None, K.EXPENSE, "#9ca3af", "help-circle"),
    # ---------- کارمزد و وام ----------
    ("bank_fee", "کارمزد بانکی", None, K.FEE, "#78716c", "percent"),
    ("loan_installment", "اقساط وام", None, K.LOAN, "#b45309", "landmark"),
    # ---------- درآمد ----------
    ("salary", "حقوق و درآمد", None, K.INCOME, "#22c55e", "wallet"),
    ("bank_interest", "سود بانکی", None, K.INCOME, "#4ade80", "trending-up"),
    ("refund", "برگشت وجه", None, K.INCOME, "#86efac", "undo"),
    ("income_unknown", "دریافت نامشخص", None, K.INCOME, "#bbf7d0", "download"),
    ("other_income", "سایر درآمد", None, K.INCOME, "#16a34a", "plus"),
    # ---------- انتقال و تعدیل ----------
    ("self_transfer", "انتقال بین حساب‌های خودم", None, K.TRANSFER, "#475569", "repeat"),
    ("transfer_out", "انتقال به دیگران", None, K.TRANSFER, "#334155", "send"),
    ("adjustment", "تعدیل و اصلاح سند", None, K.ADJUSTMENT, "#a1a1aa", "scale"),
]

# قوانین سیستمی: «نوع تراکنش» بانک → دسته
# review=True یعنی هنوز نمی‌دانیم پول دقیقاً کجا رفته و باید در صف بررسی بیاید.
# (slug قانون، نام، نوع تراکنش، slug دسته، review، is_transfer، اولویت)
TYPE_RULES: list[tuple[str, str, str, bool, bool, int]] = [
    ("کارمزد کارت به کارت", "کارمزد", "bank_fee", False, False, 10),
    ("بستهٔ اینترنت", "اینترنت", "net_package", False, False, 10),
    ("شارژ سیم‌کارت", "شارژ سیم‌کارت", "sim_charge", False, False, 10),
    ("پرداخت قبض", "قبض", "utilities", True, False, 10),
    ("قسط تسهیلات", "اقساط تسهیلات", "loan_installment", False, False, 10),
    ("سود سپرده", "واریز سود بانکی", "bank_interest", False, False, 10),
    ("برگشت وجه", "برگشت پول", "refund", False, False, 10),
    ("اصلاح سند", "اصلاح سند", "adjustment", False, False, 10),
    ("برداشت از خودپرداز", "برداشت نقدی", "cash_withdraw", False, False, 10),
    # خریدها: فروشنده ناشناس است تا وقتی کاربر پایانه را برچسب بزند
    ("خرید حضوری (نیازمند برچسب)", "خرید از فروشگاه", "uncategorized", True, False, 90),
    ("خرید اینترنتی (نیازمند برچسب)", "خرید اینترنتی", "uncategorized", True, False, 90),
    # انتقال‌های خروجی
    ("انتقال به کارت", "انتقال به کارت", "transfer_out", True, True, 80),
    ("انتقال به سپرده", "انتقال به سپرده", "transfer_out", True, True, 80),
    ("انتقال پل خروجی", "انتقال پل", "transfer_out", True, True, 80),
    # دریافت‌ها
    ("دریافت پایا", "دریافت پایا", "income_unknown", True, True, 80),
    ("دریافت پل", "دریافت پل", "income_unknown", True, True, 80),
    ("دریافت از کارت", "دریافت از کارت", "income_unknown", True, True, 80),
    ("دریافت از سپرده", "دریافت از سپرده", "income_unknown", True, True, 80),
    ("شارژ سپرده با کارت", "شارژ سپرده با کارت", "income_unknown", True, True, 80),
]

DEFAULT_SETTINGS: dict[str, str] = {
    # آستانهٔ «خردخرجی» به ریال (پیش‌فرض ۱۰۰٬۰۰۰ تومان)
    "micro_spend_threshold_rial": "1000000",
    # ضریب هشدار جهش ماهانه نسبت به میانگین ۳ ماه گذشته
    "mom_alert_factor": "1.5",
}
