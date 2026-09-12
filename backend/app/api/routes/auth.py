from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.api.deps import Auth, DB
from app.auth import (
    change_password,
    check_not_locked,
    clear_session,
    client_key,
    is_setup_required,
    issue_session,
    record_failure,
    record_success,
    setup_password,
    verify_password,
)

router = APIRouter()


class PasswordIn(BaseModel):
    password: str


@router.get("/status")
def auth_status(db: DB) -> dict:
    """عمومی: رابط با این می‌فهمد صفحهٔ «ساخت حساب» را نشان بدهد یا «ورود»."""
    return {"setup_required": is_setup_required(db)}


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(payload: PasswordIn, request: Request, response: Response, db: DB) -> dict:
    """ساخت حساب مالک — فقط وقتی هنوز رمزی ثبت نشده. بعد از آن ۴۰۹ می‌دهد."""
    setup_password(db, payload.password)
    issue_session(db, request, response)
    return {"ok": True}


@router.post("/login")
def login(payload: PasswordIn, request: Request, response: Response, db: DB) -> dict:
    if is_setup_required(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "هنوز حسابی ساخته نشده.")
    key = client_key(request)
    check_not_locked(key)
    if not verify_password(db, payload.password):
        record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "رمز عبور نادرست است.")
    record_success(key)
    issue_session(db, request, response)
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
def set_password(
    payload: PasswordChange, request: Request, response: Response, db: DB, user: Auth
) -> dict:
    """تغییر رمز. نشست‌های دیگر باطل می‌شوند؛ همین نشست کوکی تازه می‌گیرد."""
    change_password(db, payload.current_password, payload.new_password)
    issue_session(db, request, response)
    return {"ok": True}
