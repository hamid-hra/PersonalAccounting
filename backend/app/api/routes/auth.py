from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import Auth, DB
from app.auth import change_password, clear_session, issue_session, verify_password

router = APIRouter()


class LoginIn(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginIn, response: Response, db: DB) -> dict:
    if not verify_password(db, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "رمز عبور نادرست است.")
    issue_session(response)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    clear_session(response)
    return {"ok": True}


@router.get("/me")
def me(user: Auth) -> dict:
    return {"user": user}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
def set_password(payload: PasswordChange, db: DB, user: Auth) -> dict:
    """تغییر رمز از داخل برنامه — نشست فعلی باز می‌ماند."""
    change_password(db, payload.current_password, payload.new_password)
    return {"ok": True}
