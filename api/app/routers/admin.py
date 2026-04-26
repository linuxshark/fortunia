"""Admin and feedback endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import verify_internal_key
from app.models import IntentFeedback

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
