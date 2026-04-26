"""Intent feedback model for model improvement."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class IntentFeedback(Base):
    """User feedback on intent detection for model improvement."""

    __tablename__ = "intent_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_message: Mapped[str] = mapped_column(nullable=False)
    classified_as: Mapped[bool] = mapped_column(nullable=False)
    user_confirmed: Mapped[Optional[bool]] = mapped_column(nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<IntentFeedback(id={self.id}, classified_as={self.classified_as})>"
