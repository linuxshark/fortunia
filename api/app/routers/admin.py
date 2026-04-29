"""Admin and feedback endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from app.db import get_db
from app.deps import verify_internal_key
from app.models import IntentFeedback
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


class FeedbackRequest(BaseModel):
    """User feedback on intent detection."""

    raw_message: str
    classified_as: bool
    user_confirmed: bool
    reason: str = ""


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> dict:
    """Submit feedback on intent detection for model improvement."""
    feedback = IntentFeedback(
        raw_message=request.raw_message,
        classified_as=request.classified_as,
        user_confirmed=request.user_confirmed,
        reason=request.reason,
    )
    db.add(feedback)
    db.commit()
    return {"status": "recorded", "id": feedback.id}


@router.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


# ── User management ───────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    telegram_id: int
    display_name: str
    user_key: str


class UserOut(BaseModel):
    id: int
    telegram_id: int
    display_name: str
    user_key: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/users", response_model=List[UserOut])
async def list_users(
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> List[User]:
    return db.query(User).order_by(User.display_name).all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> User:
    existing = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if existing:
        existing.display_name = payload.display_name
        existing.user_key = payload.user_key
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        telegram_id=payload.telegram_id,
        display_name=payload.display_name,
        user_key=payload.user_key,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{telegram_id}")
async def deactivate_user(
    telegram_id: int,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> dict:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.is_active = False
    db.commit()
    return {"status": "deactivated", "telegram_id": telegram_id}
