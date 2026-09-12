from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StoredFile(Base):
    """
    فایل‌های آپلودشده — صورتحساب خام، رسید قسط، عکس لیست نیازها.

    داخل دیتابیس می‌مانند نه روی دیسک، تا همه‌چیز با یک pg_dump پشتیبان
    گرفته شود و برنامه روی هر سروری بدون دیسک پایدار کار کند. نام فایل
    «هش sha256 + پسوند» است؛ محتوای تکراری فقط یک بار ذخیره می‌شود.
    """

    __tablename__ = "stored_file"

    name: Mapped[str] = mapped_column(String(160), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)  # statement | receipt | wishlist
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
