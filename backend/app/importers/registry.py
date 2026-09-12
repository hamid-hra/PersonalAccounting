"""ثبت و انتخاب خودکار آداپتور بانک."""

from pathlib import Path

from app.importers.base import BankImporter

_REGISTRY: dict[str, BankImporter] = {}


def register(importer: BankImporter) -> BankImporter:
    _REGISTRY[importer.bank] = importer
    return importer


def all_importers() -> list[BankImporter]:
    return list(_REGISTRY.values())


def get(bank: str) -> BankImporter | None:
    return _REGISTRY.get(bank)


def detect(path: Path) -> BankImporter | None:
    """آداپتوری که فایل را می‌شناسد؛ None اگر هیچ‌کدام نشناسند."""
    for importer in _REGISTRY.values():
        try:
            if importer.sniff(path):
                return importer
        except Exception:
            continue
    return None
