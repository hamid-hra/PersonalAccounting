"""
آداپتور صورتحساب بانک ملی (سامانهٔ بام / همراه بام).

برخلاف سامان که فایلش xlsx است، این فایل **xls واقعی (BIFF8)** است و با
`xlrd` خوانده می‌شود.

سه چیز دارد که سامان ندارد و کیفیت داده را بالا می‌برد:
  • ستون «توضیحات» ساختاریافته است (جفت‌های «کلید : مقدار») — پس نام و شبای
    طرف مقابل مستقیم در دسترس است و لازم نیست از متن آزاد حدس زده شود.
  • «نوع : انتقال پول بين حساب هاي خود» را صریح علامت می‌زند.
  • ستون «توضیحات کاربر» یادداشت خودِ کاربر در اپ بانک است.

ساختار فایل (تأییدشده روی نمونهٔ واقعی):
  • سطرهای ۳ تا ۵: بلوک سرصفحه، «کلید:» و مقدارش در سلول‌های کنار هم
  • سطر ۸: هدر جدول
  • سطرهای بعدی: تراکنش‌ها، از جدید به قدیم
"""

import re
from pathlib import Path

import xlrd

from app.importers.base import BankImporter, ParsedStatement, RawTxn, StatementMeta
from app.importers.registry import register
from app.enums import Bank
from app.services.extract import clean_amount
from app.services.normalize import fa_digits, fold, normalize

# نگاشت متن هدر ستون → نام منطقی
_COLUMNS: list[tuple[str, str]] = [
    ("ردیف", "row_index"),
    ("تاریخ", "date"),
    ("زمان", "time"),
    ("شعبه", "branch"),
    ("نوع", "direction"),
    ("مبلغ", "amount"),
    ("شماره پیگیری", "doc_number"),
    ("اطلاعات تکمیلی", "extra"),
    ("شرح", "tx_type"),
    ("توضیحات", "details"),
    ("مانده", "balance"),
    ("کانال تراکنش", "channel"),
    ("طبقه بندی تراکنش", "bank_category"),
    ("توضیحات کاربر", "user_note"),
]
_HEADER_REQUIRED = {"row_index", "date", "amount", "balance", "direction"}

# برچسب‌های بلوک سرصفحه
_META_LABELS: list[tuple[str, str]] = [
    ("نام و نام خانوادگی", "owner_name"),
    ("کد ملی", "national_id"),
    ("شماره حساب", "account_number"),
    ("از تاریخ", "period_from"),
    ("تا تاریخ", "period_to"),
    ("تاریخ و ساعت دانلود", "downloaded_at"),
]

# کلیدهای داخل ستون «توضیحات» — با «،» از هم جدا می‌شوند
_DETAIL_KEYS: dict[str, str] = {
    "شماره حساب طرف مقابل": "counterparty_account",
    "نام کامل طرف مقابل": "counterparty_name",
    "شماره شبای طرف مقابل": "counterparty_iban",
    "بانک طرف مقابل": "counterparty_bank",
    "نام شعبه طرف مقابل": "counterparty_branch",
    "کارمزد": "fee",
    "کد رهگیری": "tracking_code",
    "شناسه واریز": "deposit_id",
    "شناسه پرداخت": "payment_id",
    "توضیحات": "note",
    "نوع": "kind",
}

# مقدار فیلد «نوع» وقتی بانک خودش انتقال داخلی را اعلام می‌کند.
# با fold() مقایسه می‌شود چون فایل «بين/هاي» عربی می‌نویسد و normalize آن را
# به «بین/های» فارسی تبدیل می‌کند.
SELF_TRANSFER_MARKER = "انتقال پول بین حساب های خود"

_DATE_RE = re.compile(r"^1[34]\d{2}[/\-]\d{1,2}[/\-]\d{1,2}")
_IBAN_RE = re.compile(r"IR\d{24}", re.IGNORECASE)


def parse_details(text: str) -> dict[str, str]:
    """
    ستون «توضیحات» را به دیکشنری تبدیل می‌کند.

    نمونهٔ واقعی:
        «شماره حساب طرف مقابل : 0200000000002،  نام کامل طرف مقابل : على
         رضايى،  نوع : انتقال پول بين حساب هاي خود»
    """
    out: dict[str, str] = {}
    if not text:
        return out
    for chunk in normalize(text).split("،"):
        if ":" not in chunk:
            continue
        raw_key, _, raw_value = chunk.partition(":")
        key = normalize(raw_key).strip()
        value = raw_value.strip()
        if not value:
            continue
        field = _DETAIL_KEYS.get(key)
        if field and field not in out:
            out[field] = value
    return out


def iban_from_account(account_number: str) -> str | None:
    """
    شماره حساب ملی → شبا، با محاسبهٔ رقم کنترل (mod-97).

    قالب شبای ایران: IR + ۲ رقم کنترل + ۳ رقم کد بانک (۰۱۷ برای ملی)
    + ۱۹ رقم شماره حساب با صفرِ ابتدا.
    برای تطبیق انتقال بین‌بانکی لازم است، چون سامان طرف مقابل را با شبا می‌نویسد.
    """
    digits = re.sub(r"\D", "", fa_digits(account_number or ""))
    if not digits:
        return None
    body = f"017{digits.zfill(19)}"
    # استاندارد IBAN: کشور و رقم کنترل به انتها می‌روند، IR→1827، صفرها موقتی
    rearranged = f"{body}1827" + "00"
    check = 98 - (int(rearranged) % 97)
    return f"IR{check:02d}{body}"


class MelliImporter(BankImporter):
    bank = Bank.MELLI
    label_fa = "بانک ملی (بام)"

    # ---------- تشخیص ----------
    def sniff(self, path: Path) -> bool:
        if path.suffix.lower() != ".xls":
            return False
        try:
            book = xlrd.open_workbook(str(path))
        except Exception:
            return False
        try:
            sheet = book.sheet_by_index(0)
            blob = " ".join(
                normalize(str(sheet.cell_value(r, c)))
                for r in range(min(sheet.nrows, 20))
                for c in range(sheet.ncols)
            )
        finally:
            book.release_resources()
        return "کانال تراکنش" in blob and "شماره پیگیری" in blob

    # ---------- پارس ----------
    def parse(self, path: Path) -> ParsedStatement:
        book = xlrd.open_workbook(str(path))
        try:
            sheet = book.sheet_by_index(0)
            grid = [
                [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                for r in range(sheet.nrows)
            ]
        finally:
            book.release_resources()

        warnings: list[str] = []
        header_idx, colmap = self._find_header(grid)
        if header_idx is None:
            raise ValueError("سطر هدر جدول تراکنش‌ها در فایل بانک ملی پیدا نشد.")

        meta = self._parse_meta(grid[:header_idx])
        txns = self._parse_rows(grid[header_idx + 1 :], colmap, warnings)
        self._fill_balances(meta, txns)
        return ParsedStatement(meta=meta, transactions=txns, warnings=warnings)

    @staticmethod
    def _fill_balances(meta: StatementMeta, txns: list[RawTxn]) -> None:
        """
        فایل ملی جمع‌ها و ماندهٔ ابتدا/انتها را در سرصفحه ندارد، ولی ستون مانده
        دارد. ماندهٔ ابتدا و انتها از خودِ سطرها ساخته می‌شود تا آزمون
        «ماندهٔ ابتدا + خالص = ماندهٔ انتها» و بررسی زنجیره واقعاً اجرا شوند.
        """
        rows = [t for t in txns if t.row_index is not None and t.balance_after_rial is not None]
        if not rows:
            return
        oldest = max(rows, key=lambda t: t.row_index)
        newest = min(rows, key=lambda t: t.row_index)
        meta.opening_balance_rial = oldest.balance_after_rial - oldest.amount_rial
        meta.closing_balance_rial = newest.balance_after_rial

    # ---------- بخش‌های داخلی ----------
    def _find_header(self, grid: list[list]) -> tuple[int | None, dict[str, int]]:
        for idx, row in enumerate(grid[:40]):
            colmap: dict[str, int] = {}
            for col, cell in enumerate(row):
                label = normalize(str(cell)).strip()
                for needle, key in _COLUMNS:
                    if key not in colmap and label == needle:
                        colmap[key] = col
                        break
            if _HEADER_REQUIRED.issubset(colmap):
                return idx, colmap
        return None, {}

    def _parse_meta(self, header_rows: list[list]) -> StatementMeta:
        meta = StatementMeta(bank=self.bank)
        found: dict[str, str] = {}

        # برچسب و مقدار در دو سلول جدا کنار هم‌اند: «شماره حساب:» | «0100000000001»
        for row in header_rows:
            for col, cell in enumerate(row):
                label = normalize(str(cell)).strip().rstrip(":").strip()
                for needle, key in _META_LABELS:
                    if key in found or label != needle:
                        continue
                    for nxt in row[col + 1 : col + 3]:
                        value = normalize(str(nxt)).strip()
                        if value:
                            found[key] = value
                            break
                    break

        meta.owner_name = found.get("owner_name")
        meta.account_number = re.sub(r"\D", "", fa_digits(found.get("account_number", "")))
        if meta.account_number:
            meta.iban = iban_from_account(meta.account_number)
        meta.period_from_jalali = self._clean_jalali(found.get("period_from"))
        meta.period_to_jalali = self._clean_jalali(found.get("period_to"))
        meta.currency = "ریال ایران"
        return meta

    @staticmethod
    def _clean_jalali(value: str | None) -> str | None:
        if not value:
            return None
        m = re.search(r"(1[34]\d{2})/(\d{1,2})/(\d{1,2})", fa_digits(value))
        return f"{int(m[1]):04d}/{int(m[2]):02d}/{int(m[3]):02d}" if m else None

    def _parse_rows(
        self, rows: list[list], colmap: dict[str, int], warnings: list[str]
    ) -> list[RawTxn]:
        def cell(row: list, key: str) -> str:
            col = colmap.get(key)
            if col is None or col >= len(row):
                return ""
            value = row[col]
            # xlrd اعداد را float می‌دهد؛ «ردیف» نباید «1.0» شود
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value).strip()

        out: list[RawTxn] = []
        for row in rows:
            date_text = fa_digits(cell(row, "date"))
            if not _DATE_RE.match(date_text):
                continue

            amount = clean_amount(cell(row, "amount"))
            direction_text = normalize(cell(row, "direction"))
            is_deposit = "واریز" in direction_text

            details_raw = cell(row, "details")
            details = parse_details(details_raw)

            # شبا گاهی فقط در ستون «اطلاعات تکمیلی» است
            extra = cell(row, "extra")
            if "counterparty_iban" not in details:
                if m := _IBAN_RE.search(fa_digits(extra)):
                    details["counterparty_iban"] = m.group().upper()

            try:
                seq = int(float(fa_digits(cell(row, "row_index"))))
            except ValueError:
                seq = None

            # شرح + توضیحات با هم، تا جست‌وجوی متنی و قوانین regex کار کنند
            description = " | ".join(
                part for part in (cell(row, "tx_type"), details_raw) if part
            )

            out.append(
                RawTxn(
                    jalali_datetime=self._combine_datetime(date_text, cell(row, "time")),
                    withdraw_rial=0 if is_deposit else amount,
                    deposit_rial=amount if is_deposit else 0,
                    balance_after_rial=clean_amount(cell(row, "balance")),
                    description_raw=description or details_raw,
                    bank_tx_type=normalize(cell(row, "tx_type")) or None,
                    doc_number=cell(row, "doc_number") or None,
                    row_index=seq,
                    is_self_declared=fold(SELF_TRANSFER_MARKER)
                    in fold(details.get("kind", "")),
                    user_note=cell(row, "user_note") or None,
                    details=details,
                )
            )

        if not out:
            warnings.append("هیچ سطر تراکنشی در فایل پیدا نشد.")
        return out

    @staticmethod
    def _combine_datetime(date_text: str, time_text: str) -> str:
        """«1405/03/18» + «19:28:37» → «1405/03/18 19:28:37»"""
        m = re.match(r"^(1[34]\d{2})[/\-](\d{1,2})[/\-](\d{1,2})", date_text)
        if not m:
            return date_text
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        t = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", fa_digits(time_text or ""))
        hh, mi, ss = (int(t[1]), int(t[2]), int(t[3] or 0)) if t else (0, 0, 0)
        return f"{y:04d}/{mo:02d}/{d:02d} {hh:02d}:{mi:02d}:{ss:02d}"


register(MelliImporter())
