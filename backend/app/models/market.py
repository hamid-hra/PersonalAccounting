from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class MarketItem(Base):
    """یک قلم قابل قیمت‌گذاری: دلار، سکه، طلای ۱۸ عیار…"""

    __tablename__ = "market_item"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)  # usd_sell، sekkeh…
    label_fa: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))  # currency | gold | coin
    unit_fa: Mapped[str] = mapped_column(String(40))  # «هر دلار»، «هر گرم»…
    is_tracked: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(default=100)


class PricePoint(Base):
    """
    قیمت یک قلم در یک روز.

    هر قیمتی که یک‌بار گرفته شد برای همیشه اینجا می‌ماند — تاریخچه بدون
    مصرف سهمیهٔ درخواست انباشته می‌شود.
    """

    __tablename__ = "price_point"
    __table_args__ = (UniqueConstraint("item_code", "price_date", name="uq_price_item_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(
        ForeignKey("market_item.code", ondelete="CASCADE"), index=True
    )
    price_date: Mapped[date] = mapped_column(Date, index=True)
    jalali_date: Mapped[str] = mapped_column(String(12))

    open_rial: Mapped[int | None] = mapped_column(BigInteger)
    high_rial: Mapped[int | None] = mapped_column(BigInteger)
    low_rial: Mapped[int | None] = mapped_column(BigInteger)
    close_rial: Mapped[int] = mapped_column(BigInteger)

    # درصد تغییر نسبت به روز قبل — سرویس آماده می‌دهد، حساب نمی‌کنیم
    change_percent: Mapped[float | None] = mapped_column(Numeric(8, 2))
    source: Mapped[str] = mapped_column(String(24), default="brsapi")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AssetHolding(Base):
    """
    دارایی‌ای که کاربر نگه داشته — «۱۰ گرم طلا خریدم».

    مقدار اعشاری است (۲.۵ گرم، ۰.۵ سکه) ولی قیمت تمام‌شده ریالِ صحیح.
    """

    __tablename__ = "asset_holding"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(
        ForeignKey("market_item.code", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[float] = mapped_column(Numeric(18, 6))
    acquired_jalali: Mapped[str] = mapped_column(String(12))
    acquired_date: Mapped[date] = mapped_column(Date, index=True)
    cost_rial: Mapped[int | None] = mapped_column(BigInteger)  # کل مبلغ پرداختی
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["MarketItem"] = relationship()


class ApiCallLog(Base):
    """
    شمارندهٔ محلی درخواست‌های API.

    سهمیهٔ رایگان نوسان ۱۲۰ درخواست در ماه است. این جدول تنها راهی است که
    قبل از زدن درخواست بفهمیم چقدر مانده — و اگر تمام شد، درخواست را
    نزنیم به‌جای اینکه خطای ۵۰۳ بگیریم.
    """

    __tablename__ = "api_call_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), index=True)
    endpoint: Mapped[str] = mapped_column(String(40))
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(String(300))


class PriceAlert(Base):
    """
    هشدار قیمتی که **خودِ کاربر** آستانه‌اش را گذاشته.

    این توصیه نیست: برنامه نمی‌گوید کی بخر یا بفروش، فقط عددی را که خودت
    تعیین کرده‌ای می‌پاید و وقتی رد شد خبر می‌دهد.
    """

    __tablename__ = "price_alert"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str] = mapped_column(
        ForeignKey("market_item.code", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(8))  # above | below
    threshold_rial: Mapped[int] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(200))

    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_price_rial: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["MarketItem"] = relationship()
