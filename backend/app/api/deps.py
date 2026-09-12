from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.auth import require_session
from app.db import get_db

DB = Annotated[Session, Depends(get_db)]
Auth = Annotated[str, Depends(require_session)]
