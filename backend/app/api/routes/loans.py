from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.enums import InstallmentStatus, LoanStatus
from app.models import Loan, LoanAttachment, LoanInstallment
from app.services import loans as svc
from app.services.jalali import parse_jalali_date, to_jalali_str

router = APIRouter()


def serialize_attachment(a: LoanAttachment) -> dict:
    return {
        "id": a.id,
        "loan_id": a.loan_id,
        "installment_id": a.installment_id,
        "url": f"/api/files/receipts/{a.stored_name}",
        "original_name": a.original_name,
        "mime_type": a.mime_type,
        "size_bytes": a.size_bytes,
        "caption": a.caption,
        "uploaded_at": a.uploaded_at.isoformat() if a.uploaded_at else None,
    }


def serialize_installment(i: LoanInstallment) -> dict:
    return {
        "id": i.id,
        "loan_id": i.loan_id,
        "seq": i.seq,
        "due_jalali": i.due_jalali,
        "due_date": i.due_date.isoformat(),
        "days_left": (i.due_date - date.today()).days,
        "amount_rial": i.amount_rial,
        "status": i.status,
        "paid_jalali": i.paid_jalali,
        "paid_amount_rial": i.paid_amount_rial,
        "transaction_id": i.transaction_id,
        "note": i.note,
        "attachments": [serialize_attachment(a) for a in i.attachments],
    }


def serialize_loan(loan: Loan, *, detail: bool = False) -> dict:
    data = {
        "id": loan.id,
        "title": loan.title,
        "lender": loan.lender,
        "loan_ref": loan.loan_ref,
        "account_id": loan.account_id,
        "principal_rial": loan.principal_rial,
        "interest_rate": float(loan.interest_rate) if loan.interest_rate is not None else None,
        "installment_count": loan.installment_count,
        "installment_amount_rial": loan.installment_amount_rial,
        "first_due_jalali": loan.first_due_jalali,
        "disbursement_transaction_id": loan.disbursement_transaction_id,
        "status": loan.status,
        "note": loan.note,
        **svc.loan_progress(loan),
    }
    if detail:
        data["installments"] = [serialize_installment(i) for i in loan.installments]
        data["attachments"] = [
            serialize_attachment(a) for a in loan.attachments if a.installment_id is None
        ]
    return data


# ---------------------------------------------------------------- وام
class LoanIn(BaseModel):
    title: str
    lender: str | None = None
    loan_ref: str | None = None
    account_id: int | None = None
    principal_rial: int | None = None
    interest_rate: float | None = None
    installment_count: int
    installment_amount_rial: int
    first_due_jalali: str
    disbursement_transaction_id: int | None = None
    note: str | None = None


@router.get("")
def list_loans(db: DB, user: Auth) -> list[dict]:
    svc.refresh_statuses(db)
    db.commit()
    loans = db.scalars(select(Loan).order_by(Loan.id.desc()))
    return [serialize_loan(loan) for loan in loans]


@router.get("/suggested-disbursements")
def suggested_disbursements(db: DB, user: Auth) -> list[dict]:
    """واریزی‌هایی که به‌نظر دریافت وام‌اند و هنوز ثبت نشده‌اند."""
    return svc.suggest_disbursements(db)


@router.post("/{loan_id}/autolink")
def autolink(loan_id: int, db: DB, user: Auth) -> dict:
    """اقساط را از روی تراکنش‌های بانکی پیدا و «پرداخت‌شده» علامت می‌زند."""
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام پیدا نشد.")
    linked = svc.autolink_installments(db, loan)
    db.refresh(loan)
    return {"linked": linked, "loan": serialize_loan(loan, detail=True)}


@router.get("/upcoming")
def upcoming(db: DB, user: Auth, within_days: int = 10) -> list[dict]:
    rows = svc.upcoming_installments(db, within_days)
    db.commit()
    return rows


@router.get("/{loan_id}")
def get_loan(loan_id: int, db: DB, user: Auth) -> dict:
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام پیدا نشد.")
    svc.refresh_statuses(db, loan)
    db.commit()
    return serialize_loan(loan, detail=True)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_loan(payload: LoanIn, db: DB, user: Auth) -> dict:
    if payload.installment_count < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعداد اقساط باید دست‌کم ۱ باشد.")
    if payload.installment_amount_rial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ قسط باید مثبت باشد.")
    try:
        parse_jalali_date(payload.first_due_jalali)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    loan = Loan(**payload.model_dump(), status=LoanStatus.ACTIVE)
    db.add(loan)
    db.flush()
    for inst in svc.build_schedule(loan):
        db.add(inst)
    db.flush()
    svc.refresh_statuses(db, loan)
    db.commit()
    db.refresh(loan)
    return serialize_loan(loan, detail=True)


class LoanPatch(BaseModel):
    title: str | None = None
    lender: str | None = None
    loan_ref: str | None = None
    status: str | None = None
    note: str | None = None
    principal_rial: int | None = None
    interest_rate: float | None = None
    # تغییر این سه، جدول اقساط را بازمی‌سازد
    installment_count: int | None = None
    installment_amount_rial: int | None = None
    first_due_jalali: str | None = None


SCHEDULE_FIELDS = {"installment_count", "installment_amount_rial", "first_due_jalali"}


@router.patch("/{loan_id}")
def update_loan(loan_id: int, payload: LoanPatch, db: DB, user: Auth) -> dict:
    """
    ویرایش وام.

    اگر تعداد اقساط، مبلغ قسط یا اولین سررسید عوض شود جدول بازسازی می‌شود،
    ولی **اقساط پرداخت‌شده و رسیدهایشان دست‌نخورده می‌مانند** — تاریخچهٔ
    پرداخت واقعی است و نباید با یک ویرایش از بین برود.
    """
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام پیدا نشد.")

    data = payload.model_dump(exclude_unset=True)
    if data.get("installment_count") is not None and data["installment_count"] < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعداد اقساط باید دست‌کم ۱ باشد.")
    if (
        data.get("installment_amount_rial") is not None
        and data["installment_amount_rial"] <= 0
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ قسط باید مثبت باشد.")
    if "first_due_jalali" in data and data["first_due_jalali"]:
        try:
            parse_jalali_date(data["first_due_jalali"])
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    reschedule = any(f in data and data[f] is not None for f in SCHEDULE_FIELDS)
    for field, value in data.items():
        setattr(loan, field, value)

    result = {"rescheduled": False, "kept_paid": 0, "removed": 0}
    if reschedule:
        result = svc.reschedule(db, loan)

    db.commit()
    db.refresh(loan)
    return {**serialize_loan(loan, detail=True), "reschedule": result}


@router.delete("/{loan_id}")
def delete_loan(loan_id: int, db: DB, user: Auth) -> dict:
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام پیدا نشد.")
    for attachment in list(loan.attachments):
        svc.delete_receipt_file(db, attachment)
    db.delete(loan)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- اقساط
class PayIn(BaseModel):
    paid_jalali: str | None = None
    paid_amount_rial: int | None = None
    transaction_id: int | None = None
    note: str | None = None


@router.post("/installments/{installment_id}/pay")
def mark_paid(installment_id: int, payload: PayIn, db: DB, user: Auth) -> dict:
    inst = db.get(LoanInstallment, installment_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قسط پیدا نشد.")

    paid_jalali = payload.paid_jalali or to_jalali_str(date.today())
    try:
        inst.paid_date = parse_jalali_date(paid_jalali)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    inst.paid_jalali = paid_jalali
    inst.paid_amount_rial = payload.paid_amount_rial or inst.amount_rial
    inst.transaction_id = payload.transaction_id
    inst.status = InstallmentStatus.PAID
    if payload.note is not None:
        inst.note = payload.note

    # آخرین قسط که پرداخت شد، وام تسویه است
    loan = inst.loan
    if all(i.status == InstallmentStatus.PAID for i in loan.installments):
        loan.status = LoanStatus.SETTLED
    db.commit()
    return serialize_installment(inst)


@router.post("/installments/{installment_id}/unpay")
def mark_unpaid(installment_id: int, db: DB, user: Auth) -> dict:
    inst = db.get(LoanInstallment, installment_id)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قسط پیدا نشد.")
    inst.status = InstallmentStatus.PENDING
    inst.paid_jalali = None
    inst.paid_date = None
    inst.paid_amount_rial = None
    inst.transaction_id = None
    if inst.loan.status == LoanStatus.SETTLED:
        inst.loan.status = LoanStatus.ACTIVE
    svc.refresh_statuses(db, inst.loan)
    db.commit()
    return serialize_installment(inst)


# ---------------------------------------------------------------- رسیدها
@router.post("/{loan_id}/receipts", status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    loan_id: int,
    db: DB,
    user: Auth,
    file: UploadFile = File(...),
    installment_id: int | None = Form(default=None),
    caption: str | None = Form(default=None),
) -> dict:
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام پیدا نشد.")
    if installment_id is not None:
        inst = db.get(LoanInstallment, installment_id)
        if inst is None or inst.loan_id != loan_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "این قسط متعلق به این وام نیست.")

    content = await file.read()
    try:
        stored_name, mime, size, digest = svc.save_receipt(
            content, file.filename or "receipt", file.content_type or ""
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    attachment = LoanAttachment(
        loan_id=loan_id,
        installment_id=installment_id,
        stored_name=stored_name,
        original_name=file.filename or "receipt",
        mime_type=mime,
        size_bytes=size,
        sha256=digest,
        caption=caption,
    )
    db.add(attachment)
    db.commit()
    return serialize_attachment(attachment)


@router.delete("/receipts/{attachment_id}")
def delete_receipt(attachment_id: int, db: DB, user: Auth) -> dict:
    attachment = db.get(LoanAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید پیدا نشد.")
    svc.delete_receipt_file(db, attachment)
    db.delete(attachment)
    db.commit()
    return {"ok": True}
