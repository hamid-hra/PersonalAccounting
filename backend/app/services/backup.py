"""
پشتیبان‌گیری از داخل خود برنامه.

هر پشتیبان یک پوشه با دو فایل است:
  • database.sql.gz — خروجی pg_dump
  • data.tar.gz     — صورتحساب‌های خام و رسیدهای اقساط

فایل‌های خام هم لازم‌اند: بدون آن‌ها اگر دیتابیس را از نو بسازی،
اسکرین‌شات رسیدها و اکسل‌های اصلی از دست می‌روند.
"""

import gzip
import os
import shutil
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app.config import settings
from app.services.jalali import to_jalali_str


def backups_dir() -> Path:
    path = settings.data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pg_env() -> tuple[list[str], dict]:
    """پارامترهای اتصال از DATABASE_URL — رمز از راه محیط، نه خط فرمان."""
    url = urlparse(settings.database_url.replace("postgresql+psycopg://", "postgresql://"))
    cmd = [
        "pg_dump",
        "-h", url.hostname or "db",
        "-p", str(url.port or 5432),
        "-U", url.username or "postgres",
        "-d", (url.path or "/postgres").lstrip("/"),
        "--no-owner",
        "--no-acl",
    ]
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    return cmd, env


def create_backup() -> dict:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = backups_dir() / stamp
    target.mkdir(parents=True, exist_ok=True)

    try:
        cmd, env = _pg_env()
        dump = subprocess.run(cmd, capture_output=True, env=env, timeout=600)
        if dump.returncode != 0:
            raise RuntimeError(
                dump.stderr.decode("utf-8", "replace")[:400] or "pg_dump ناموفق بود."
            )
        with gzip.open(target / "database.sql.gz", "wb") as fh:
            fh.write(dump.stdout)

        # فایل‌های خام — پوشهٔ backups خودش داخل آرشیو نرود
        with tarfile.open(target / "data.tar.gz", "w:gz") as tar:
            for name in ("statements", "receipts"):
                folder = settings.data_dir / name
                if folder.exists():
                    tar.add(folder, arcname=name)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise

    return describe(target)


def describe(folder: Path) -> dict:
    files = [f for f in folder.iterdir() if f.is_file()]
    size = sum(f.stat().st_size for f in files)
    created = datetime.fromtimestamp(folder.stat().st_mtime)
    return {
        "name": folder.name,
        "created_at": created.isoformat(timespec="seconds"),
        "created_jalali": to_jalali_str(created.date()),
        "size_bytes": size,
        "files": sorted(f.name for f in files),
    }


def list_backups() -> list[dict]:
    return sorted(
        (describe(p) for p in backups_dir().iterdir() if p.is_dir()),
        key=lambda b: b["name"],
        reverse=True,
    )


def delete_backup(name: str) -> bool:
    """حذف یک پشتیبان. نام اعتبارسنجی می‌شود تا از پوشه بیرون نزند."""
    folder = (backups_dir() / name).resolve()
    if folder.parent != backups_dir().resolve() or not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True


def prune(keep: int = 10) -> int:
    """فقط N پشتیبان آخر نگه داشته می‌شود تا دیسک پر نشود."""
    removed = 0
    for entry in list_backups()[keep:]:
        if delete_backup(entry["name"]):
            removed += 1
    return removed
