from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import Bank, CategorizedBy, ImportStatus


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(primary_key=True)
    bank: Mapped[str] = mapped_column(String(20), default=Bank.OTHER)
    title: Mapped[str] = mapped_column(String(160))
    iban: Mapped[str | None] = mapped_column(String(34), unique=True)
    account_number: Mapped[str | None] = mapped_column(String(40))
    owner_name: Mapped[str | None] = mapped_column(String(160))
    opened_at_jalali: Mapped[str | None] = mapped_column(String(12))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OwnerAlias(Base):
    """
    هویت‌های «خودِ من».

    ۴۲٪ خروجی حساب در نمونهٔ واقعی، انتقال بین حساب‌های خود کاربر بود.
    هر تراکنشی که طرف‌حسابش با یکی از این‌ها بخواند، از تحلیل هزینه حذف می‌شود.
    """

    __tablename__ = "owner_alias"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_owner_alias_kind_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(24))  # name | card | iban | deposit_no
    value: Mapped[str] = mapped_column(String(200))
    value_norm: Mapped[str] = mapped_column(String(200), index=True)
    note: Mapped[str | None] = mapped_column(String(200))


class StatementImport(Base):
    __tablename__ = "statement_import"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("account.id", ondelete="SET NULL"), index=True
    )
    bank: Mapped[str] = mapped_column(String(20))
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default=ImportStatus.PENDING)

    period_from_jalali: Mapped[str | None] = mapped_column(String(20))
    period_to_jalali: Mapped[str | None] = mapped_column(String(20))
    opening_balance_rial: Mapped[int | None] = mapped_column(BigInteger)
    closing_balance_rial: Mapped[int | None] = mapped_column(BigInteger)
    header_total_deposit_rial: Mapped[int | None] = mapped_column(BigInteger)
    header_total_withdraw_rial: Mapped[int | None] = mapped_column(BigInteger)

    rows_total: Mapped[int] = mapped_column(Integer, default=0)
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)

    validation: Mapped[str | None] = mapped_column(Text)  # JSON گزارش اعتبارسنجی
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["Account | None"] = relationship()


class Transaction(Base):
    __tablename__ = "transaction"
    __table_args__ = (
        UniqueConstraint("account_id", "dedup_hash", name="uq_tx_account_dedup"),
        Index("ix_tx_account_occurred", "account_id", "occurred_at"),
        Index("ix_tx_review", "needs_review"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id", ondelete="CASCADE"))
    import_id: Mapped[int | None] = mapped_column(
        ForeignKey("statement_import.id", ondelete="SET NULL")
    )

    # ---- زمان ----
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), index=True)
    occurred_date: Mapped[date] = mapped_column(Date, index=True)
    jalali_datetime: Mapped[str] = mapped_column(String(24))  # «1405/06/10 18:42:09»
    jalali_year: Mapped[int] = mapped_column(Integer, index=True)
    jalali_month: Mapped[int] = mapped_column(Integer, index=True)
    jalali_day: Mapped[int] = mapped_column(Integer)

    # ---- مبلغ (ریالِ صحیح، علامت‌دار: منفی = برداشت) ----
    amount_rial: Mapped[int] = mapped_column(BigInteger, index=True)
    direction: Mapped[str] = mapped_column(String(4), index=True)
    balance_after_rial: Mapped[int | None] = mapped_column(BigInteger)

    # ---- دادهٔ خام بانک ----
    bank_tx_type: Mapped[str | None] = mapped_column(String(60), index=True)
    doc_number: Mapped[str | None] = mapped_column(String(40), index=True)
    row_index: Mapped[int | None] = mapped_column(Integer)
    description_raw: Mapped[str] = mapped_column(Text)
    description_norm: Mapped[str] = mapped_column(Text)

    # ---- موجودیت‌های استخراج‌شده از شرح سند ----
    counterparty_name: Mapped[str | None] = mapped_column(String(200))
    counterparty_name_norm: Mapped[str | None] = mapped_column(String(200), index=True)
    counterparty_iban: Mapped[str | None] = mapped_column(String(34), index=True)
    counterparty_card: Mapped[str | None] = mapped_column(String(20), index=True)
    counterparty_bank: Mapped[str | None] = mapped_column(String(60))
    terminal_id: Mapped[str | None] = mapped_column(String(24), index=True)
    terminal_kind: Mapped[str | None] = mapped_column(String(24))
    deposit_no: Mapped[str | None] = mapped_column(String(32), index=True)
    phone_number: Mapped[str | None] = mapped_column(String(16), index=True)
    biller_id: Mapped[str | None] = mapped_column(String(32), index=True)
    loan_ref: Mapped[str | None] = mapped_column(String(32), index=True)
    trace_ref: Mapped[str | None] = mapped_column(String(40), index=True)

    # ---- دسته‌بندی ----
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), index=True
    )
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), index=True
    )
    categorized_by: Mapped[str] = mapped_column(String(12), default=CategorizedBy.NONE)
    # بعضی بانک‌ها (ملی) خودشان می‌گویند «انتقال پول بين حساب هاي خود» —
    # این حدس نیست، اعلام خودِ بانک است و بر همهٔ قواعد دیگر مقدم می‌شود.
    is_self_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    is_self_transfer: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # سه‌حالته: True = درآمد است، False = درآمد نیست، None = هنوز تصمیم نگرفته‌ای.
    # هر واریزی درآمد نیست — وام، قرض و پس‌گرفتن پول هم واریز می‌شوند.
    is_income: Mapped[bool | None] = mapped_column(Boolean, index=True)
    # حواله‌ای که برگشت خورده — نه هزینه است نه درآمد
    is_reversed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)

    dedup_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped["Account"] = relationship()
    category: Mapped["Category | None"] = relationship()  # noqa: F821
    contact: Mapped["Contact | None"] = relationship()  # noqa: F821
