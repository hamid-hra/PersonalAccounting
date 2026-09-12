"""
قرارداد مشترک همهٔ آداپتورهای بانکی.

افزودن یک بانک جدید (بلو، ملی، مهر) = ساختن یک فایل در همین پوشه که
`BankImporter` را پیاده کند و خودش را در registry ثبت کند. هیچ‌جای دیگری
از برنامه لازم نیست تغییر کند.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.services.normalize import normalize


@dataclass
class RawTxn:
    """یک سطر تراکنش، همان‌طور که در فایل بانک آمده — بدون تفسیر."""

    jalali_datetime: str
    withdraw_rial: int
    deposit_rial: int
    balance_after_rial: int | None
    description_raw: str
    bank_tx_type: str | None = None
    doc_number: str | None = None
    row_index: int | None = None
    # بانک ملی صریحاً «انتقال پول بين حساب هاي خود» را علامت می‌زند
    is_self_declared: bool = False
    # یادداشتی که خود کاربر در اپ بانک روی تراکنش نوشته
    user_note: str | None = None
    # موجودیت‌هایی که آداپتور مستقیم از ستون‌های ساختاریافته خوانده و
    # نباید از متن آزاد حدس زده شوند (بانک ملی این‌ها را آماده می‌دهد)
    details: dict | None = None

    @property
    def amount_rial(self) -> int:
        """علامت‌دار: منفی = برداشت."""
        return self.deposit_rial - self.withdraw_rial

    @property
    def direction(self) -> str:
        return "in" if self.amount_rial >= 0 else "out"

    def dedup_hash(self) -> str:
        """
        کلید یکتای سطر.

        روی نمونهٔ واقعیِ ۱۲۱۵ سطری، چهارتایی (تاریخ، برداشت، واریز، مانده)
        ۱۰۰٪ یکتا بود — برخلاف «شماره سند» که بین سطر کارمزد و سطر اصلی
        مشترک است. شرح سند هم اضافه شده تا حاشیهٔ اطمینان بیشتر شود.
        """
        parts = "|".join(
            [
                self.jalali_datetime,
                str(self.withdraw_rial),
                str(self.deposit_rial),
                str(self.balance_after_rial if self.balance_after_rial is not None else ""),
                normalize(self.description_raw),
            ]
        )
        return hashlib.sha256(parts.encode("utf-8")).hexdigest()


@dataclass
class StatementMeta:
    """اطلاعات سرصفحهٔ صورتحساب — برای ساخت/تشخیص حساب و اعتبارسنجی."""

    bank: str
    owner_name: str | None = None
    iban: str | None = None
    account_number: str | None = None
    opened_at_jalali: str | None = None
    period_from_jalali: str | None = None
    period_to_jalali: str | None = None
    opening_balance_rial: int | None = None
    closing_balance_rial: int | None = None
    total_deposit_rial: int | None = None
    total_withdraw_rial: int | None = None
    currency: str | None = None


@dataclass
class ParsedStatement:
    meta: StatementMeta
    transactions: list[RawTxn] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BankImporter(ABC):
    """پایهٔ همهٔ آداپتورها."""

    bank: str
    label_fa: str

    @abstractmethod
    def sniff(self, path: Path) -> bool:
        """آیا این فایل متعلق به این بانک است؟"""

    @abstractmethod
    def parse(self, path: Path) -> ParsedStatement:
        """فایل را به سرصفحه + فهرست تراکنش تبدیل می‌کند."""

    def validate(self, parsed: ParsedStatement) -> dict:
        """
        بررسی سلامت داده: جمع‌ها و مانده باید با سرصفحهٔ خود فایل بخواند.
        این تنها راه اطمینان از درستیِ پارس است، بدون اعتماد کورکورانه.

        نکته: در صورتحساب واقعی سامان، چند سطرِ هم‌زمان مانده‌ی جاافتاده دارند
        (مثلاً یک خرید و «اصلاح سند»ِ برگشتی‌اش یک مانده نشان می‌دهند). این
        اختلاف‌ها جفت‌به‌جفت خنثی می‌شوند و ایراد پارس نیستند؛ پس به‌عنوان
        هشدار گزارش می‌شوند نه خطا. آنچه باید دقیق بخواند، جمع‌ها و ماندهٔ
        پایانی است.
        """
        meta, txns = parsed.meta, parsed.transactions
        sum_dep = sum(t.deposit_rial for t in txns)
        sum_wd = sum(t.withdraw_rial for t in txns)
        checks: list[dict] = []

        def check(name: str, expected, actual, level: str = "error") -> None:
            if expected is None:
                checks.append({"name": name, "status": "skipped", "detail": "در فایل نبود"})
                return
            ok = expected == actual
            checks.append(
                {
                    "name": name,
                    "status": "ok" if ok else ("mismatch" if level == "error" else "warn"),
                    "expected": expected,
                    "actual": actual,
                }
            )

        check("جمع کل واریز", meta.total_deposit_rial, sum_dep)
        check("جمع کل برداشت", meta.total_withdraw_rial, sum_wd)

        # سطرها از جدید به قدیم‌اند؛ زنجیره از قدیمی‌ترین سطر ساخته می‌شود.
        ordered = sorted(txns, key=lambda t: t.row_index or 0, reverse=True)
        local_breaks = 0
        if meta.opening_balance_rial is not None:
            running = meta.opening_balance_rial
            for t in ordered:
                running += t.amount_rial
                if t.balance_after_rial is not None and running != t.balance_after_rial:
                    local_breaks += 1
                    running = t.balance_after_rial  # همگام‌سازی دوباره با خود فایل
            checks.append(
                {
                    "name": "پرش موضعی در ستون مانده",
                    "status": "ok" if local_breaks == 0 else "warn",
                    "expected": 0,
                    "actual": local_breaks,
                    "detail": "سطرهای هم‌زمان که بانک ماندهٔ یکسان ثبت کرده — بی‌خطر",
                }
            )
            # آزمون اصلی: ماندهٔ اول + خالص تراکنش‌ها باید دقیقاً ماندهٔ آخر شود.
            check(
                "ماندهٔ ابتدا + خالص = ماندهٔ انتها",
                meta.closing_balance_rial,
                meta.opening_balance_rial + sum_dep - sum_wd,
            )

        check(
            "ماندهٔ پایانی سطر آخر",
            meta.closing_balance_rial,
            ordered[-1].balance_after_rial if ordered else None,
        )

        duplicates = len(txns) - len({t.dedup_hash() for t in txns})
        checks.append(
            {
                "name": "یکتایی کلید تشخیص تکرار",
                "status": "ok" if duplicates == 0 else "mismatch",
                "expected": 0,
                "actual": duplicates,
            }
        )

        return {
            "checks": checks,
            "rows": len(txns),
            "sum_deposit_rial": sum_dep,
            "sum_withdraw_rial": sum_wd,
            "warnings": parsed.warnings,
            "ok": all(c["status"] != "mismatch" for c in checks),
        }
