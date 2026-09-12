from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import InstallmentStatus, LoanStatus


class Loan(Base):
    __tablename__ = "loan"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    lender: Mapped[str | None] = mapped_column(String(160))
    loan_ref: Mapped[str | None] = mapped_column(String(40), index=True)  # مثل LN_0000123456
    account_id: Mapped[int | None] = mapped_column(ForeignKey("account.id", ondelete="SET NULL"))

    principal_rial: Mapped[int | None] = mapped_column(BigInteger)
    interest_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    installment_count: Mapped[int] = mapped_column(Integer)
    installment_amount_rial: Mapped[int] = mapped_column(BigInteger)

    first_due_jalali: Mapped[str] = mapped_column(String(12))  # «1404/07/06»
    # تراکنشی که خودِ وام با آن به حساب آمد («تسهيلات مالي» در بانک ملی)
    disbursement_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(12), default=LoanStatus.ACTIVE)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    installments: Mapped[list["LoanInstallment"]] = relationship(
        back_populates="loan", cascade="all, delete-orphan", order_by="LoanInstallment.seq"
    )
    attachments: Mapped[list["LoanAttachment"]] = relationship(
        back_populates="loan", cascade="all, delete-orphan"
    )


class LoanInstallment(Base):
    __tablename__ = "loan_installment"
    __table_args__ = (UniqueConstraint("loan_id", "seq", name="uq_installment_seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loan.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)

    due_jalali: Mapped[str] = mapped_column(String(12))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    amount_rial: Mapped[int] = mapped_column(BigInteger)

    status: Mapped[str] = mapped_column(String(12), default=InstallmentStatus.PENDING, index=True)
    paid_jalali: Mapped[str | None] = mapped_column(String(12))
    paid_date: Mapped[date | None] = mapped_column(Date)
    paid_amount_rial: Mapped[int | None] = mapped_column(BigInteger)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)

    loan: Mapped["Loan"] = relationship(back_populates="installments")
    attachments: Mapped[list["LoanAttachment"]] = relationship(
        back_populates="installment", cascade="all, delete-orphan"
    )


class LoanAttachment(Base):
    """اسکرین‌شات رسید پرداخت قسط."""

    __tablename__ = "loan_attachment"

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_id: Mapped[int] = mapped_column(ForeignKey("loan.id", ondelete="CASCADE"), index=True)
    installment_id: Mapped[int | None] = mapped_column(
        ForeignKey("loan_installment.id", ondelete="CASCADE"), index=True
    )
    stored_name: Mapped[str] = mapped_column(String(160))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    caption: Mapped[str | None] = mapped_column(String(300))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    loan: Mapped["Loan"] = relationship(back_populates="attachments")
    installment: Mapped["LoanInstallment | None"] = relationship(back_populates="attachments")
