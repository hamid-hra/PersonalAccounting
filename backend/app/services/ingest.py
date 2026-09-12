"""
ورود صورتحساب: فایل اکسل → تراکنش‌های دسته‌بندی‌شده در دیتابیس.

سه تضمین مهم:
  • تکراری وارد نمی‌شود — کلید یکتای هر سطر روی نمونهٔ واقعی آزموده شده است.
  • حساب از روی شبای داخل فایل تشخیص داده یا ساخته می‌شود.
  • نام صاحب حساب خودکار به فهرست «حساب‌های خودم» اضافه می‌شود تا انتقال‌های
    داخلی از همان اولین ورود از تحلیل هزینه کنار بروند.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import Bank, ImportStatus
from app.importers import detect, get
from app.importers.base import BankImporter, ParsedStatement, RawTxn
from app.models import Account, OwnerAlias, StatementImport, Transaction
from app.services import filestore
from app.services.categorize import Categorizer
from app.services.links import detect_links
from app.services.extract import extract
from app.services.jalali import jalali_parts, parse_jalali
from app.services.normalize import fold, fold_name, normalize


@dataclass
class ImportReport:
    import_id: int
    account_id: int
    bank: str
    rows_total: int
    rows_inserted: int
    rows_duplicate: int
    validation: dict


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def store_upload(db: Session, src: Path, original_name: str) -> tuple[str, str]:
    """فایل خام را برای آرشیو در دیتابیس نگه می‌دارد؛ نام بر پایهٔ هش تا تکراری جمع نشود."""
    suffix = Path(original_name).suffix.lower() or ".xlsx"
    mime = {
        ".xls": "application/vnd.ms-excel",
    }.get(suffix, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    content = src.read_bytes()
    name = filestore.put(db, filestore.STATEMENT, content, suffix, mime)
    return name, name[:64]


def pick_importer(path: Path, bank: str | None) -> BankImporter:
    importer = get(bank) if bank else detect(path)
    if importer is None:
        raise ValueError(
            "این فایل با هیچ‌کدام از بانک‌های پشتیبانی‌شده نخواند. "
            "فعلاً صورتحساب بانک سامان (xlsx) و بانک ملی/بام (xls) پشتیبانی می‌شود."
        )
    return importer


def find_account(db: Session, parsed: ParsedStatement) -> Account | None:
    """حساب موجودِ متناظر با این صورتحساب — بدون ساختن حساب تازه."""
    meta = parsed.meta
    if meta.iban:
        account = db.scalar(select(Account).where(Account.iban == meta.iban))
        if account:
            return account
    if meta.account_number:
        return db.scalar(
            select(Account).where(
                Account.bank == meta.bank, Account.account_number == meta.account_number
            )
        )
    return None


def resolve_account(db: Session, parsed: ParsedStatement) -> Account:
    meta = parsed.meta
    account = find_account(db, parsed)
    if account is None:
        from app.enums import BANK_LABELS_FA

        label = BANK_LABELS_FA.get(Bank(meta.bank), meta.bank)
        title = f"{label} — {meta.account_number or meta.iban or 'بدون شماره'}"
        account = Account(
            bank=meta.bank,
            title=title,
            iban=meta.iban,
            account_number=meta.account_number,
            owner_name=meta.owner_name,
            opened_at_jalali=meta.opened_at_jalali,
        )
        db.add(account)
        db.flush()
    return account


def ensure_owner_aliases(db: Session, parsed: ParsedStatement) -> None:
    """نام صاحب حساب و شبای همین حساب = «خودم»."""
    meta = parsed.meta
    wanted: list[tuple[str, str, str]] = []
    if meta.owner_name:
        wanted.append(("name", meta.owner_name, fold_name(meta.owner_name)))
    if meta.iban:
        wanted.append(("iban", meta.iban, fold(meta.iban)))
    if meta.account_number:
        wanted.append(("deposit_no", meta.account_number, fold(meta.account_number)))

    for kind, value, norm in wanted:
        exists = db.scalar(
            select(OwnerAlias).where(OwnerAlias.kind == kind, OwnerAlias.value == value)
        )
        if exists is None:
            db.add(
                OwnerAlias(
                    kind=kind, value=value, value_norm=norm, note="از سرصفحهٔ صورتحساب"
                )
            )
    db.flush()


def build_transaction(raw: RawTxn, account_id: int, import_id: int) -> Transaction:
    occurred_at, jalali_dt = parse_jalali(raw.jalali_datetime)
    year, month, day = jalali_parts(raw.jalali_datetime)
    info = extract(raw.description_raw)

    # آنچه آداپتور از ستون ساختاریافته خوانده، بر حدسِ regex مقدم است.
    # بانک ملی نام و شبای طرف مقابل را آماده می‌دهد؛ حدس‌زدن از متن آزاد
    # فقط شانس خطا اضافه می‌کند.
    details = raw.details or {}
    if name := details.get("counterparty_name"):
        info.counterparty_name = normalize(name)
        info.counterparty_name_norm = fold_name(name)
    if iban := details.get("counterparty_iban"):
        info.counterparty_iban = iban.upper()
    if account := details.get("counterparty_account"):
        info.deposit_no = account
    if bank := details.get("counterparty_bank"):
        info.counterparty_bank = bank
    if tracking := details.get("tracking_code"):
        info.trace_ref = info.trace_ref or tracking

    return Transaction(
        account_id=account_id,
        import_id=import_id,
        occurred_at=occurred_at,
        occurred_date=occurred_at.date(),
        jalali_datetime=jalali_dt,
        jalali_year=year,
        jalali_month=month,
        jalali_day=day,
        amount_rial=raw.amount_rial,
        direction=raw.direction,
        balance_after_rial=raw.balance_after_rial,
        bank_tx_type=raw.bank_tx_type,
        doc_number=raw.doc_number,
        row_index=raw.row_index,
        description_raw=raw.description_raw,
        description_norm=normalize(raw.description_raw),
        counterparty_name=info.counterparty_name,
        counterparty_name_norm=info.counterparty_name_norm,
        counterparty_iban=info.counterparty_iban,
        counterparty_card=info.counterparty_card,
        counterparty_bank=info.counterparty_bank,
        terminal_id=info.terminal_id,
        terminal_kind=info.terminal_kind,
        deposit_no=info.deposit_no,
        phone_number=info.phone_number,
        biller_id=info.biller_id,
        loan_ref=info.loan_ref,
        trace_ref=info.trace_ref,
        is_self_declared=raw.is_self_declared,
        note=raw.user_note,
        dedup_hash=raw.dedup_hash(),
    )


def preview_import(
    db: Session, tmp_path: Path, original_name: str, bank: str | None = None
) -> dict:
    """
    فایل را می‌خواند و گزارش می‌دهد **بدون آنکه چیزی بنویسد**.

    تا قبل از این، برنامه اول می‌نوشت بعد می‌گفت چند تا تکراری بود. حالا
    قبل از هر نوشتنی می‌بینی چه اتفاقی می‌افتد — و مهم‌تر، هشدار می‌گیری
    اگر قرار باشد حساب تازه‌ای ساخته شود، چون آن تنها راه واقعیِ
    دوباره‌شمرده‌شدن یک تراکنش است.
    """
    importer = pick_importer(tmp_path, bank)
    parsed = importer.parse(tmp_path)
    validation = importer.validate(parsed)
    meta = parsed.meta

    account = find_account(db, parsed)
    warnings: list[dict] = []

    if account is None:
        warnings.append(
            {
                "level": "warn",
                "text": "حسابی با این شبا/شماره در برنامه نیست و حساب تازه ساخته می‌شود. "
                "اگر این همان حساب قبلی است، اول شبایش را در تنظیمات کامل کن، "
                "وگرنه تراکنش‌ها دو بار شمرده می‌شوند.",
            }
        )
        duplicate = 0
        new_rows = len(parsed.transactions)
    else:
        seen = set(
            db.scalars(
                select(Transaction.dedup_hash).where(Transaction.account_id == account.id)
            )
        )
        digests = [raw.dedup_hash() for raw in parsed.transactions]
        duplicate = sum(1 for d in digests if d in seen)
        new_rows = len(digests) - duplicate

        overlaps = db.scalars(
            select(StatementImport).where(
                StatementImport.account_id == account.id,
                StatementImport.status == ImportStatus.COMMITTED,
            )
        )
        for previous in overlaps:
            if _periods_overlap(
                meta.period_from_jalali,
                meta.period_to_jalali,
                previous.period_from_jalali,
                previous.period_to_jalali,
            ):
                warnings.append(
                    {
                        "level": "info",
                        "text": f"دورهٔ این فایل با فایل «{previous.original_name}» "
                        f"({previous.period_from_jalali} تا {previous.period_to_jalali}) "
                        "هم‌پوشانی دارد. تراکنش‌های مشترک دوباره وارد نمی‌شوند.",
                    }
                )
                break

    if duplicate and not new_rows:
        warnings.append(
            {"level": "info", "text": "همهٔ سطرهای این فایل قبلاً وارد شده‌اند."}
        )

    return {
        "bank": importer.bank,
        "bank_label": importer.label_fa,
        "account_id": account.id if account else None,
        "account_title": account.title if account else None,
        "creates_account": account is None,
        "owner_name": meta.owner_name,
        "iban": meta.iban,
        "account_number": meta.account_number,
        "period_from_jalali": meta.period_from_jalali,
        "period_to_jalali": meta.period_to_jalali,
        "rows_total": len(parsed.transactions),
        "rows_new": new_rows,
        "rows_duplicate": duplicate,
        "validation": validation,
        "warnings": warnings,
    }


def _periods_overlap(a_from, a_to, b_from, b_to) -> bool:
    """هم‌پوشانی دو بازهٔ جلالی — رشته‌ها با هم قابل مقایسه‌اند چون yyyy/mm/dd اند."""
    if not all((a_from, a_to, b_from, b_to)):
        return False
    return a_from <= b_to and b_from <= a_to


def import_statement(
    db: Session, tmp_path: Path, original_name: str, bank: str | None = None
) -> ImportReport:
    importer = pick_importer(tmp_path, bank)
    parsed = importer.parse(tmp_path)
    validation = importer.validate(parsed)

    stored_name, digest = store_upload(db, tmp_path, original_name)
    account = resolve_account(db, parsed)
    ensure_owner_aliases(db, parsed)

    meta = parsed.meta
    record = StatementImport(
        account_id=account.id,
        bank=importer.bank,
        original_name=original_name,
        stored_path=stored_name,
        file_sha256=digest,
        period_from_jalali=meta.period_from_jalali,
        period_to_jalali=meta.period_to_jalali,
        opening_balance_rial=meta.opening_balance_rial,
        closing_balance_rial=meta.closing_balance_rial,
        header_total_deposit_rial=meta.total_deposit_rial,
        header_total_withdraw_rial=meta.total_withdraw_rial,
        rows_total=len(parsed.transactions),
        validation=json.dumps(validation, ensure_ascii=False),
        status=ImportStatus.PENDING,
    )
    db.add(record)
    db.flush()

    seen: set[str] = set(
        db.scalars(select(Transaction.dedup_hash).where(Transaction.account_id == account.id))
    )
    categorizer = Categorizer(db)

    inserted = duplicate = 0
    for raw in parsed.transactions:
        digest_row = raw.dedup_hash()
        if digest_row in seen:
            duplicate += 1
            continue
        seen.add(digest_row)
        tx = build_transaction(raw, account.id, record.id)
        categorizer.apply(tx)
        db.add(tx)
        inserted += 1

    record.rows_inserted = inserted
    record.rows_duplicate = duplicate
    record.status = ImportStatus.COMMITTED
    db.commit()

    # با آمدن حساب تازه، انتقال‌های بین‌بانکی و برگشتی‌ها تازه قابل کشف می‌شوند
    if inserted:
        detect_links(db)

    return ImportReport(
        import_id=record.id,
        account_id=account.id,
        bank=importer.bank,
        rows_total=len(parsed.transactions),
        rows_inserted=inserted,
        rows_duplicate=duplicate,
        validation=validation,
    )
