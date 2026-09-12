import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.models import StatementImport
from app.services.ingest import import_statement, preview_import

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# سامان xlsx می‌دهد، بانک ملی xls قدیمی (BIFF8)
ALLOWED_SUFFIXES = {".xlsx", ".xlsm", ".xls"}


async def _to_temp(file: UploadFile) -> tuple[bytes, str]:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "فقط فایل اکسل (xlsx یا xls) پذیرفته می‌شود."
        )
    body = await file.read()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "فایل بیش از حد بزرگ است.")
    return body, suffix


@router.post("/preview")
async def preview_statement(db: DB, user: Auth, file: UploadFile = File(...)) -> dict:
    """
    فایل را می‌خواند و می‌گوید چه اتفاقی می‌افتد — **بدون نوشتن**.

    چند سطر تازه است، چند تا تکراری، و آیا حساب تازه‌ای ساخته می‌شود.
    """
    body, suffix = await _to_temp(file)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(body)
        tmp.flush()
        try:
            return preview_import(db, Path(tmp.name), file.filename or "statement.xlsx")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("")
async def upload_statement(db: DB, user: Auth, file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "فقط فایل اکسل (xlsx یا xls) پذیرفته می‌شود."
        )

    body = await file.read()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "فایل بیش از حد بزرگ است.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(body)
        tmp.flush()
        try:
            report = import_statement(db, Path(tmp.name), file.filename or "statement.xlsx")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    return {
        "import_id": report.import_id,
        "account_id": report.account_id,
        "bank": report.bank,
        "rows_total": report.rows_total,
        "rows_inserted": report.rows_inserted,
        "rows_duplicate": report.rows_duplicate,
        "validation": report.validation,
    }


@router.get("")
def list_imports(db: DB, user: Auth) -> list[dict]:
    out = []
    for i in db.scalars(select(StatementImport).order_by(StatementImport.id.desc())):
        out.append(
            {
                "id": i.id,
                "account_id": i.account_id,
                "bank": i.bank,
                "original_name": i.original_name,
                "status": i.status,
                "period_from_jalali": i.period_from_jalali,
                "period_to_jalali": i.period_to_jalali,
                "rows_total": i.rows_total,
                "rows_inserted": i.rows_inserted,
                "rows_duplicate": i.rows_duplicate,
                "validation": json.loads(i.validation) if i.validation else None,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
        )
    return out
