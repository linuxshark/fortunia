"""FastAPI dependencies."""

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from .config import Settings


async def verify_internal_key(x_internal_key: str = Header(None)) -> str:
    """Verify internal API key."""
    settings = Settings()
    if x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_internal_key


def resolve_user_key(telegram_id: int | None, fallback_user_id: str, db: Session) -> str:
    """
    Resolve a telegram_id to a user_key.

    If telegram_id is provided, looks up the User table and raises 403 if not found/inactive.
    Falls back to fallback_user_id when telegram_id is None (legacy support).
    """
    from .models.user import User

    if telegram_id is None:
        return fallback_user_id
    user: User | None = db.query(User).filter_by(telegram_id=telegram_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=403, detail="Telegram user not authorized")
    return user.user_key
