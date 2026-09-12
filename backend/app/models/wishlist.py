from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import WishPriority


class WishItem(Base):
    """
    چیزی که لازم دارم و هنوز نخریده‌ام.

    برخلاف بودجه که دربارهٔ گذشته است، این دربارهٔ آینده است: چه می‌خواهم،
    چقدر می‌ارزد، و تا کِی. بعد از خرید می‌شود به تراکنش واقعی وصلش کرد تا
    **قیمت واقعی در برابر برآورد** دیده شود.
    """

    __tablename__ = "wish_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    estimated_rial: Mapped[int | None] = mapped_column(BigInteger)
    priority: Mapped[str] = mapped_column(
        String(16), default=WishPriority.NICE, index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("category.id", ondelete="SET NULL"), index=True
    )

    deadline_jalali: Mapped[str | None] = mapped_column(String(12))
    deadline_date: Mapped[date | None] = mapped_column(Date, index=True)

    url: Mapped[str | None] = mapped_column(Text)
    image_name: Mapped[str | None] = mapped_column(String(160))

    is_bought: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    bought_jalali: Mapped[str | None] = mapped_column(String(12))
    bought_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transaction.id", ondelete="SET NULL")
    )

    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["Category | None"] = relationship()  # noqa: F821
    bought_transaction: Mapped["Transaction | None"] = relationship()  # noqa: F821

    @property
    def actual_rial(self) -> int | None:
        """قیمتی که واقعاً پرداخت شد — از تراکنش وصل‌شده."""
        tx = self.bought_transaction
        return abs(tx.amount_rial) if tx else None
