from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Auth, DB
from app.services import appsettings, backup
from app.models import AppSetting, OwnerAlias
from app.services.categorize import recategorize_all
from app.services.normalize import fold, fold_name

router = APIRouter()


@router.get("")
def get_settings(db: DB, user: Auth) -> dict:
    return {s.key: s.value for s in db.scalars(select(AppSetting))}


class SettingsPatch(BaseModel):
    values: dict[str, str]


@router.patch("")
def update_settings(payload: SettingsPatch, db: DB, user: Auth) -> dict:
    for key, value in payload.values.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return {s.key: s.value for s in db.scalars(select(AppSetting))}


# ---------------------------------------------------------------- خودم
@router.get("/owner-aliases")
def list_aliases(db: DB, user: Auth) -> list[dict]:
    return [
        {"id": a.id, "kind": a.kind, "value": a.value, "note": a.note}
        for a in db.scalars(select(OwnerAlias).order_by(OwnerAlias.id))
    ]


class AliasIn(BaseModel):
    kind: str  # name | card | iban | deposit_no
    value: str
    note: str | None = None


@router.post("/owner-aliases", status_code=status.HTTP_201_CREATED)
def add_alias(payload: AliasIn, db: DB, user: Auth) -> dict:
    if payload.kind not in {"name", "card", "iban", "deposit_no"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع شناسه معتبر نیست.")
    value = payload.value.strip()
    if not value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مقدار لازم است.")

    exists = db.scalar(
        select(OwnerAlias).where(OwnerAlias.kind == payload.kind, OwnerAlias.value == value)
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "این مورد قبلاً ثبت شده است.")

    norm = fold_name(value) if payload.kind == "name" else fold(value)
    alias = OwnerAlias(kind=payload.kind, value=value, value_norm=norm, note=payload.note)
    db.add(alias)
    db.commit()

    # گذشته هم باید به‌روز شود: تراکنش‌هایی که تا الان هزینه شمرده می‌شدند
    # ممکن است در واقع انتقال داخلی باشند.
    updated = recategorize_all(db)
    return {"id": alias.id, "recategorized": updated}


@router.delete("/owner-aliases/{alias_id}")
def delete_alias(alias_id: int, db: DB, user: Auth) -> dict:
    alias = db.get(OwnerAlias, alias_id)
    if alias is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیدا نشد.")
    db.delete(alias)
    db.commit()
    return {"ok": True, "recategorized": recategorize_all(db)}


@router.post("/recategorize")
def recategorize(db: DB, user: Auth, force: bool = False) -> dict:
    """اجرای دوبارهٔ دسته‌بندی روی همهٔ تراکنش‌ها."""
    return {"updated": recategorize_all(db, force=force)}


# ---------------------------------------------------------------- پشتیبان‌گیری
@router.get("/backups")
def list_backups(user: Auth) -> list[dict]:
    return backup.list_backups()


@router.post("/backups", status_code=status.HTTP_201_CREATED)
def create_backup(user: Auth, keep: int = Query(10, ge=1, le=200)) -> dict:
    """
    یک پشتیبان تازه می‌سازد و قدیمی‌ترها را هرس می‌کند.

    شامل دیتابیس و فایل‌های خام (صورتحساب‌ها و رسیدها) — بدون فایل‌ها،
    بازیابی ناقص است.
    """
    try:
        created = backup.create_backup()
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"پشتیبان‌گیری ناموفق بود: {exc}"
        ) from exc
    pruned = backup.prune(keep)
    return {"backup": created, "pruned": pruned}


@router.get("/backups/{name}/{filename}")
def download_backup(name: str, filename: str, user: Auth):
    folder = (backup.backups_dir() / name).resolve()
    path = (folder / filename).resolve()
    # مسیر باید واقعاً داخل پوشهٔ پشتیبان باشد
    if folder.parent != backup.backups_dir().resolve() or path.parent != folder:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مسیر نامعتبر است.")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فایل پیدا نشد.")
    return FileResponse(path, filename=f"{name}-{filename}")


@router.delete("/backups/{name}")
def delete_backup(name: str, user: Auth) -> dict:
    if not backup.delete_backup(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پشتیبان پیدا نشد.")
    return {"ok": True}


# ---------------------------------------------------------------- سرویس قیمت
@router.get("/market")
def market_settings(db: DB, user: Auth) -> dict:
    """
    تنظیمات سرویس قیمت.

    کلیدها هرگز کامل برنمی‌گردند — فقط چند نویسهٔ آخرشان، تا بدانی کدام
    کلید ثبت شده بدون آنکه راز از سرور بیرون برود.
    """
    from app.services.market.service import all_providers

    snapshot = appsettings.public_snapshot(db)
    return {**snapshot, "providers": all_providers()}


class MarketConfig(BaseModel):
    provider: str | None = None
    brsapi_key: str | None = None
    navasan_key: str | None = None


@router.put("/market")
def update_market_settings(payload: MarketConfig, db: DB, user: Auth) -> dict:
    from app.services.market.service import _PROVIDER_CLASSES

    if payload.provider is not None:
        if payload.provider not in _PROVIDER_CLASSES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "این سرویس شناخته نمی‌شود.")
        appsettings.set(db, appsettings.MARKET_PROVIDER, payload.provider)

    # رشتهٔ خالی یعنی «کلید را پاک کن»؛ None یعنی «دست نزن»
    for value, key in (
        (payload.brsapi_key, appsettings.BRSAPI_KEY),
        (payload.navasan_key, appsettings.NAVASAN_KEY),
    ):
        if value is not None:
            appsettings.set(db, key, value.strip())

    return market_settings(db, user)
