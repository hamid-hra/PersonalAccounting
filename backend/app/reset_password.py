"""
رمز فراموش شده؟ این دستور رمز را پاک می‌کند تا دوباره صفحهٔ «ساخت حساب»
بیاید. هیچ داده‌ای حذف نمی‌شود.

    docker compose exec backend python -m app.reset_password
"""

from app.auth import reset_password
from app.db import SessionLocal

if __name__ == "__main__":
    with SessionLocal() as db:
        reset_password(db)
    print("رمز پاک شد. مرورگر را باز کن و رمز تازه بگذار.")
