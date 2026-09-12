"""آداپتورهای بانکی. هر ماژول با import شدن خودش را ثبت می‌کند."""

from app.importers import melli, saman  # noqa: F401
from app.importers.registry import all_importers, detect, get, register

__all__ = ["all_importers", "detect", "get", "register"]
