"""
انبار فایل — روی دیتابیس.

هر فایلی که کاربر آپلود می‌کند (صورتحساب، رسید، عکس) این‌جا می‌نشیند.
چرا دیتابیس و نه دیسک: روی سرورهای ابری دیسک کانتینر با هر deploy پاک
می‌شود، ولی دیتابیس می‌ماند؛ و پشتیبان‌گیری هم فقط یک pg_dump است.
"""

import hashlib
import mimetypes
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StoredFile

STATEMENT = "statement"
RECEIPT = "receipt"
WISHLIST = "wishlist"


def name_for(content: bytes, suffix: str) -> str:
    return f"{hashlib.sha256(content).hexdigest()}{suffix.lower()}"


def put(db: Session, kind: str, content: bytes, suffix: str, mime_type: str) -> str:
    """ذخیره؛ اگر همین محتوا قبلاً هست، همان نام برمی‌گردد. commit با تماس‌گیرنده."""
    name = name_for(content, suffix)
    if db.get(StoredFile, name) is None:
        db.add(
            StoredFile(
                name=name, kind=kind, mime_type=mime_type,
                size_bytes=len(content), content=content,
            )
        )
        db.flush()
    return name


def get(db: Session, name: str) -> StoredFile | None:
    return db.get(StoredFile, name)


def exists(db: Session, name: str) -> bool:
    return db.scalar(select(StoredFile.name).where(StoredFile.name == name)) is not None


def delete(db: Session, name: str) -> None:
    row = db.get(StoredFile, name)
    if row is not None:
        db.delete(row)
        db.flush()


def import_legacy_dir(db: Session, folder: Path, kind: str) -> int:
    """
    فایل‌های نسخه‌های قبلی که روی دیسک بودند را یک‌بار به دیتابیس می‌آورد.
    idempotent — در هر بالا آمدن اجرا می‌شود و فقط تازه‌ها را اضافه می‌کند.
    """
    if not folder.is_dir():
        return 0
    moved = 0
    for path in folder.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        if exists(db, path.name):
            continue
        content = path.read_bytes()
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        # نام قدیمی هم هش+پسوند بود؛ همان را نگه می‌داریم تا ارجاع‌ها نشکند
        db.add(StoredFile(name=path.name, kind=kind, mime_type=mime,
                          size_bytes=len(content), content=content))
        moved += 1
    db.flush()
    return moved
