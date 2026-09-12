from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import DebtDirection, DebtEntryKind, DebtStatus


class Debt(Base):
    """
    قرض بین من و یک شخص.

    یک مدل برای هر دو جهت: «قرض دادم» (طلبکارم) و «قرض گرفتم» (بدهکارم).
    برخلاف وام بانکی، قرض جدول اقساط از پیش تعیین‌شده ندارد — هر بازپرداخت
    وقتی اتفاق افتاد ثبت می‌شود.
    """

    __tablename__ = "debt"

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), index=True
    )
    # اگر مخاطب ثبت نشده باشد، دست‌کم نامش را نگه می‌داریم
    person_name: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(16), index=True)

    # پول از کدام حساب رد و بدل شد؟ تهی + is_cash یعنی نقدی بوده.
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("account.id", ondelete="SET NULL"), index=True
    )
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)

    principal_rial: Mapped[int] = mapped_column(BigInteger)
    opened_jalali: Mapped[str] = mapped_column(String(12))
    opened_date: Mapped[date] = mapped_column(Date, index=True)
    due_jalali: Mapped[str | None] = mapped_column(String(12))

    status: Mapped[str] = mapped_column(String(12), default=DebtStatus.OPEN, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contact: Mapped["Contact | None"] = relationship()  # noqa: F821
    account: Mapped["Account | None"] = relationship()  # noqa: F821
    entries: Mapped[list["DebtEntry"]] = relationship(
        back_populates="debt", cascade="all, delete-orphan", order_by="DebtEntry.entry_date"
    )

    @property
    def repaid_rial(self) -> int:
        return sum(e.amount_rial for e in self.entries if e.kind == DebtEntryKind.REPAYMENT)

    @property
    def outstanding_rial(self) -> int:
        return self.principal_rial - self.repaid_rial

    @property
    def is_settled(self) -> bool:
        return self.outstanding_rial <= 0


class DebtEntry(Base):
    """یک رویداد روی قرض — اصل مبلغ یا یک بازپرداخت، معمولاً وصل به تراکنش."""

    __tablename__ = "debt_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debt.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(12), default=DebtEntryKind.REPAYMENT)
    amount_rial: Mapped[int] = mapped_column(BigInteger)
    entry_jalali: Mapped[str] = mapped_column(String(12))
    entry_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)

    debt: Mapped["Debt"] = relationship(back_populates="entries")
    transaction: Mapped["Transaction | None"] = relationship()  # noqa: F821
