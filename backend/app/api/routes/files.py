"""
سرو فایل‌های آپلودشده (رسید اقساط) — پشت گیت ورود.

قبلاً با StaticFiles بدون ورود سرو می‌شد؛ روی سرور یعنی هرکس آدرس را
داشت می‌توانست رسید بانکی را ببیند. نام فایل هش sha256 است، پس الگوی
سخت‌گیرانه هم جلوی هر شکل path traversal را می‌گیرد.
"""

import re

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import Auth
from app.config import settings

router = APIRouter()

_SAFE_NAME = re.compile(r"^[0-9a-f]{64}\.[a-z0-9]{1,5}$")


@router.get("/receipts/{name}")
def receipt_file(name: str, user: Auth) -> FileResponse:
    if not _SAFE_NAME.match(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد.")
    path = settings.receipts_dir / name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد.")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})
