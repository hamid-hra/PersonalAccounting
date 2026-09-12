from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TxLink(Base):
    """
    پیوند بین دو تراکنش.

    سه چیز را می‌گیرد که بدون آن‌ها آمار غلط می‌شود:

    • `cross_account` — یک انتقال بین دو حساب خودم که در هر دو صورتحساب
      ظاهر شده. اگر جفت نشود، یک جابه‌جایی ساده هم «هزینه» و هم «درآمد»
      شمرده می‌شود.
    • `reversal` — حواله‌ای که برگشت خورده (ساتنا/پایای ناموفق). در دادهٔ
      واقعی حدود ۷۰۰ میلیون تومان درآمد و هزینهٔ خیالی می‌ساخت.
    • `fee` — کارمزدی که سطر جدا دارد ولی متعلق به یک تراکنش دیگر است.
    """

    __tablename__ = "tx_link"
    __table_args__ = (
        UniqueConstraint("kind", "primary_tx_id", "secondary_tx_id", name="uq_tx_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)

    # برای cross_account و reversal: primary = خروجی، secondary = ورودی
    # برای fee: primary = تراکنش اصلی، secondary = سطر کارمزد
    primary_tx_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id", ondelete="CASCADE"), index=True
    )
    secondary_tx_id: Mapped[int] = mapped_column(
        ForeignKey("transaction.id", ondelete="CASCADE"), index=True
    )

    amount_rial: Mapped[int] = mapped_column(BigInteger)
    seconds_apart: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    matched_by: Mapped[str] = mapped_column(String(120))

    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    primary_tx: Mapped["Transaction"] = relationship(  # noqa: F821
        foreign_keys=[primary_tx_id]
    )
    secondary_tx: Mapped["Transaction"] = relationship(  # noqa: F821
        foreign_keys=[secondary_tx_id]
    )
