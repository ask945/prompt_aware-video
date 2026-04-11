from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import bearer_scheme, get_current_user
from database.db import get_db
from database.service import (
    authenticate_user,
    create_token,
    create_user,
    list_videos_for_user,
    revoke_token,
)


router = APIRouter()


class AuthRequest(BaseModel):
    email: str
    password: str


def _validate_credentials(payload: AuthRequest) -> tuple[str, str]:
    email = payload.email.strip().lower()
    password = payload.password.strip()

    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    return email, password


@router.post("/api/auth/signup")
async def signup(payload: AuthRequest, db: Session = Depends(get_db)):
    email, password = _validate_credentials(payload)

    try:
        user = create_user(db, email, password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    token = create_token(db, user["id"])
    return {"token": token, "user": user}


@router.post("/api/auth/login")
async def login(payload: AuthRequest, db: Session = Depends(get_db)):
    email, password = _validate_credentials(payload)
    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_token(db, user["id"])
    return {"token": token, "user": user}


@router.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@router.post("/api/auth/logout")
async def logout(
    credentials=Depends(bearer_scheme),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if credentials and credentials.credentials:
        revoke_token(db, credentials.credentials)
    return {"status": "ok", "user_id": current_user["id"]}


@router.get("/api/videos")
async def get_my_videos(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"videos": list_videos_for_user(db, current_user["id"])}
