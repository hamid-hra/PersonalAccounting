"""وام‌ها: تولید جدول اقساط، وضعیت سررسید، و ذخیرهٔ رسیدها."""

from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import InstallmentStatus, LoanStatus
from app.models import Loan, LoanAttachment, LoanInstallment
from app.services import filestore
from app.services.jalali import (
    add_months,
    jalali_parts,
    parse_jalali_date,
    to_jalali_str,
    today_jalali_parts,
)

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


def build_schedule(loan: Loan) -> list[LoanInstallment]:
    """
    از «اولین سررسید + تعداد اقساط» جدول می‌سازد.

    ماه‌های جلالی طول یکسان ندارند؛ اگر روز سررسید ۳۱ باشد و ماه بعد ۳۰ روزه،
    قسط به آخرین روز آن ماه می‌چسبد (نه اینکه به ماه بعد سر برود).
    """
    year, month, day = jalali_parts(loan.first_due_jalali)
    out: list[LoanInstallment] = []
    for seq in range(loan.installment_count):
        y, m, d = add_months(year, month, day, seq)
        due_jalali = f"{y:04d}/{m:02d}/{d:02d}"
        out.append(
            LoanInstallment(
                loan=loan,
                seq=seq + 1,
                due_jalali=due_jalali,
                due_date=parse_jalali_date(due_jalali),
                amount_rial=loan.installment_amount_rial,
                status=InstallmentStatus.PENDING,
            )
        )
    return out


def refresh_statuses(db: Session, loan: Loan | None = None) -> int:
    """قسطی که سررسیدش گذشته و پرداخت نشده، معوق می‌شود."""
    today = date.today()
    stmt = select(LoanInstallment).where(
        LoanInstallment.status != InstallmentStatus.PAID
    )
    if loan is not None:
        stmt = stmt.where(LoanInstallment.loan_id == loan.id)

    changed = 0
    for inst in db.scalars(stmt):
        target = (
            InstallmentStatus.OVERDUE if inst.due_date < today else InstallmentStatus.PENDING
        )
        if inst.status != target:
            inst.status = target
            changed += 1
    db.flush()
    return changed


def loan_progress(loan: Loan) -> dict:
    paid = [i for i in loan.installments if i.status == InstallmentStatus.PAID]
    overdue = [i for i in loan.installments if i.status == InstallmentStatus.OVERDUE]
    pending = [i for i in loan.installments if i.status == InstallmentStatus.PENDING]
    total = sum(i.amount_rial for i in loan.installments)
    paid_amount = sum(i.paid_amount_rial or i.amount_rial for i in paid)
    next_due = min(pending, key=lambda i: i.due_date, default=None)

    return {
        "paid_count": len(paid),
        "overdue_count": len(overdue),
        "pending_count": len(pending),
        "total_rial": total,
        "paid_rial": paid_amount,
        "remaining_rial": total - paid_amount,
        "progress": (len(paid) / len(loan.installments)) if loan.installments else 0,
        "next_due_jalali": next_due.due_jalali if next_due else None,
        "next_due_days": (next_due.due_date - date.today()).days if next_due else None,
        "next_due_amount_rial": next_due.amount_rial if next_due else None,
    }


def upcoming_installments(db: Session, within_days: int = 10) -> list[dict]:
    """اقساطی که نزدیک سررسیدند یا معوق شده‌اند — برای هشدار داشبورد."""
    refresh_statuses(db)
    today = date.today()
    rows = db.scalars(
        select(LoanInstallment)
        .where(LoanInstallment.status != InstallmentStatus.PAID)
        .order_by(LoanInstallment.due_date)
    )
    out = []
    for inst in rows:
        days = (inst.due_date - today).days
        if days > within_days:
            continue
        out.append(
            {
                "installment_id": inst.id,
                "loan_id": inst.loan_id,
                "loan_title": inst.loan.title,
                "seq": inst.seq,
                "due_jalali": inst.due_jalali,
                "days_left": days,
                "amount_rial": inst.amount_rial,
                "status": inst.status,
            }
        )
    return out


def save_receipt(
    db: Session, content: bytes, filename: str, content_type: str
) -> tuple[str, str, int, str]:
    """
    رسید را در دیتابیس با نام مبتنی بر هش ذخیره می‌کند تا آپلود تکراری فضا نگیرد.
    خروجی: (نام ذخیره‌شده، mime، حجم، sha256)
    """
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("فقط تصویر (PNG/JPG/WebP) یا PDF پذیرفته می‌شود.")
    if len(content) > MAX_RECEIPT_BYTES:
        raise ValueError("حجم فایل بیش از ۱۰ مگابایت است.")

    stored_name = filestore.put(
        db, filestore.RECEIPT, content, ALLOWED_IMAGE_TYPES[content_type], content_type
    )
    return stored_name, content_type, len(content), stored_name[:64]


def delete_receipt_file(db: Session, attachment: LoanAttachment) -> None:
    """فایل فیزیکی فقط وقتی حذف می‌شود که هیچ رسید دیگری به آن اشاره نکند."""
    others = db.scalar(
        select(LoanAttachment).where(
            LoanAttachment.stored_name == attachment.stored_name,
            LoanAttachment.id != attachment.id,
        )
    )
    if others is None:
        filestore.delete(db, attachment.stored_name)


# ---------------------------------------------------------------- تشخیص خودکار
# عبارت‌هایی که یعنی «بانک به من وام داد»
DISBURSEMENT_WORDS = ("تسهیلات مالی", "پرداخت تسهیلات", "اعطای تسهیلات")


def suggest_disbursements(db: Session) -> list[dict]:
    """
    واریزی‌هایی که به‌نظر می‌رسد دریافت وام‌اند.

    در فایل واقعی بانک ملی یک «تسهيلات مالي» ۳۰۰ میلیون تومانی هست که خود
    کاربر هم کنارش نوشته «واممم» — چنین چیزی نباید در «درآمد» گم شود.
    """
    from app.models import Transaction

    rows = db.scalars(
        select(Transaction)
        .where(Transaction.amount_rial > 0)
        .order_by(Transaction.occurred_at.desc())
    )
    taken = {
        loan.disbursement_transaction_id
        for loan in db.scalars(select(Loan))
        if loan.disbursement_transaction_id
    }

    out = []
    for tx in rows:
        blob = f"{tx.bank_tx_type or ''} {tx.description_norm or ''}"
        if not any(word in blob for word in DISBURSEMENT_WORDS):
            continue
        if tx.id in taken:
            continue
        out.append(
            {
                "transaction_id": tx.id,
                "jalali_datetime": tx.jalali_datetime,
                "amount_rial": tx.amount_rial,
                "bank_tx_type": tx.bank_tx_type,
                "note": tx.note,
                "description": tx.description_raw[:160],
            }
        )
    return out


def autolink_installments(db: Session, loan: Loan) -> int:
    """
    اقساط پرداخت‌شده را از روی تراکنش‌های بانکی پیدا و وصل می‌کند.

    دو شاهد، به‌ترتیب اعتماد:
      ۱. شمارهٔ تسهیلات (`LN_…`) که بانک در شرح سند می‌نویسد — قطعی است.
      ۲. مبلغِ برابر در پنجرهٔ ±۱۰ روزِ سررسید، به شرطی که آن تراکنش قبلاً
         به قسط دیگری وصل نشده باشد.
    """
    from app.models import Transaction

    used = {
        i.transaction_id
        for i in db.scalars(select(LoanInstallment))
        if i.transaction_id
    }
    linked = 0

    for inst in loan.installments:
        if inst.status == InstallmentStatus.PAID or inst.transaction_id:
            continue

        candidates = list(
            db.scalars(
                select(Transaction).where(
                    Transaction.amount_rial < 0,
                    Transaction.occurred_date >= inst.due_date - timedelta(days=10),
                    Transaction.occurred_date <= inst.due_date + timedelta(days=10),
                )
            )
        )

        match = None
        if loan.loan_ref:
            match = next(
                (t for t in candidates if t.loan_ref == loan.loan_ref and t.id not in used),
                None,
            )
        if match is None:
            match = next(
                (
                    t
                    for t in candidates
                    if abs(t.amount_rial) == inst.amount_rial and t.id not in used
                ),
                None,
            )
        if match is None:
            continue

        inst.transaction_id = match.id
        inst.status = InstallmentStatus.PAID
        inst.paid_date = match.occurred_date
        inst.paid_jalali = match.jalali_datetime.split(" ")[0]
        inst.paid_amount_rial = abs(match.amount_rial)
        used.add(match.id)
        linked += 1

    if all(i.status == InstallmentStatus.PAID for i in loan.installments):
        loan.status = LoanStatus.SETTLED
    db.commit()
    return linked


def reschedule(db: Session, loan: Loan) -> dict:
    """
    بازسازی جدول اقساط بعد از ویرایش وام.

    قسط‌های پرداخت‌شده حفظ می‌شوند — با مبلغ و تاریخِ واقعیِ پرداخت و
    رسیدهایشان. فقط قسط‌های پرداخت‌نشده دور ریخته و از نو ساخته می‌شوند.
    اگر تعداد اقساط از تعداد پرداخت‌شده‌ها کمتر شود، پرداخت‌شده‌ها باز هم
    می‌مانند و وام «تسویه» علامت می‌خورد.
    """
    paid = [i for i in loan.installments if i.status == InstallmentStatus.PAID]
    pending = [i for i in loan.installments if i.status != InstallmentStatus.PAID]

    removed = len(pending)
    for inst in pending:
        db.delete(inst)
    db.flush()

    year, month, day = jalali_parts(loan.first_due_jalali)
    taken = {i.seq for i in paid}

    for seq in range(1, loan.installment_count + 1):
        if seq in taken:
            continue
        y, m, d = add_months(year, month, day, seq - 1)
        due_jalali = f"{y:04d}/{m:02d}/{d:02d}"
        db.add(
            LoanInstallment(
                loan_id=loan.id,
                seq=seq,
                due_jalali=due_jalali,
                due_date=parse_jalali_date(due_jalali),
                amount_rial=loan.installment_amount_rial,
                status=InstallmentStatus.PENDING,
            )
        )
    db.flush()
    db.refresh(loan)
    refresh_statuses(db, loan)
    return {"rescheduled": True, "kept_paid": len(paid), "removed": removed}
