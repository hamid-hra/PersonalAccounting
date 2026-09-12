import os
import sys
from pathlib import Path

# تست‌ها نباید به دیتابیس واقعی یا پوشهٔ /data دست بزنند
os.environ.setdefault("DATA_DIR", "/tmp/pa-tests")
Path("/tmp/pa-tests/statements").mkdir(parents=True, exist_ok=True)
Path("/tmp/pa-tests/receipts").mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
import app.models  # noqa: F401  ثبت همهٔ جدول‌ها

SAMPLE = Path(__file__).parent / "sample_saman.xlsx"
SAMPLE_SAMAN = SAMPLE
SAMPLE_MELLI = Path(__file__).parent / "sample_melli.xls"


@pytest.fixture
def db():
    """دیتابیس درون‌حافظه‌ای برای تست منطق دسته‌بندی."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
