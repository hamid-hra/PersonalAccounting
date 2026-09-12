"""
سرو فایل‌های آپلودشده (رسید اقساط) — از دیتابیس، پشت گیت ورود.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.api.deps import Auth, DB
from app.services import filestore

router = APIRouter()


@router.get("/receipts/{name}")
def receipt_file(name: str, db: DB, user: Auth) -> Response:
    stored = filestore.get(db, name)
    if stored is None or stored.kind != filestore.RECEIPT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد.")
    return Response(
        stored.content, media_type=stored.mime_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
