from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import CategoryKind, ContactKind, IdentifierKind


class Category(Base):
    """درخت دسته‌بندی هزینه/درآمد."""

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), index=True
    )
    name_fa: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default=CategoryKind.EXPENSE)
    color: Mapped[str] = mapped_column(String(16), default="#64748b")
    icon: Mapped[str | None] = mapped_column(String(40))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    parent: Mapped["Category | None"] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list["Category"]] = relationship(back_populates="parent")


class Contact(Base):
    """فروشنده یا شخصِ طرف‌حساب، با یک دستهٔ پیش‌فرض."""

    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_fa: Mapped[str] = mapped_column(String(200))
    name_norm: Mapped[str] = mapped_column(String(200), index=True)
    # کلیدِ بی‌اعتنا به ترتیب کلمه — بانک‌ها یک نفر را دو جور می‌نویسند
    name_key: Mapped[str | None] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(16), default=ContactKind.PERSON)

    # دستهٔ پیش‌فرض جدا برای هر جهت.
    # «اگر از این مخاطب پول آمد، حقوقم است» ولی وقتی به او پول می‌دهم
    # ممکن است چیز دیگری باشد — یک دسته برای هر دو کافی نیست.
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), index=True
    )
    income_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL")
    )

    phone: Mapped[str | None] = mapped_column(String(20))
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["Category | None"] = relationship(foreign_keys=[category_id])
    income_category: Mapped["Category | None"] = relationship(foreign_keys=[income_category_id])
    identifiers: Mapped[list["ContactIdentifier"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )

    def category_for(self, direction: str) -> int | None:
        """دستهٔ مناسب بر اساس جهت پول."""
        if direction == "in" and self.income_category_id:
            return self.income_category_id
        return self.category_id


class ContactIdentifier(Base):
    """
    قلب «یک‌بار برچسب بزن».

    هر شناسه‌ای که در شرح سند پیدا می‌شود (شمارهٔ پایانه، کارت، شبا، سپرده، تلفن)
    به یک فروشنده وصل می‌شود؛ از آن پس همهٔ تراکنش‌های گذشته و آیندهٔ آن شناسه
    خودکار دسته‌بندی می‌شوند.
    """

    __tablename__ = "contact_identifier"
    __table_args__ = (UniqueConstraint("kind", "value", name="uq_identifier_kind_value"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    value: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contact: Mapped["Contact"] = relationship(back_populates="identifiers")


class Rule(Base):
    """قانون دسته‌بندی. قوانین سیستمی seed می‌شوند و کاربر می‌تواند ویرایش کند."""

    __tablename__ = "rule"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # ---- شرط‌ها (هرکدام None باشد یعنی بی‌اهمیت) ----
    match_bank_tx_type: Mapped[str | None] = mapped_column(String(60))
    match_description_regex: Mapped[str | None] = mapped_column(Text)
    match_counterparty_regex: Mapped[str | None] = mapped_column(Text)
    match_direction: Mapped[str | None] = mapped_column(String(8))
    match_amount_min: Mapped[int | None] = mapped_column(BigInteger)
    match_amount_max: Mapped[int | None] = mapped_column(BigInteger)

    # ---- اکشن‌ها ----
    set_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL")
    )
    set_contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL")
    )
    set_is_transfer: Mapped[bool | None] = mapped_column(Boolean)
    set_needs_review: Mapped[bool | None] = mapped_column(Boolean)

    category: Mapped["Category | None"] = relationship()


class Budget(Base):
    """سقف ماهانهٔ هر دسته. month=None یعنی پیش‌فرضِ همهٔ ماه‌ها."""

    __tablename__ = "budget"
    __table_args__ = (
        UniqueConstraint("category_id", "jalali_year", "jalali_month", name="uq_budget_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"))
    jalali_year: Mapped[int | None] = mapped_column(Integer)
    jalali_month: Mapped[int | None] = mapped_column(Integer)
    amount_rial: Mapped[int] = mapped_column(BigInteger)

    category: Mapped["Category"] = relationship()


class AppSetting(Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
