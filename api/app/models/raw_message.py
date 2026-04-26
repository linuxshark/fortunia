"""Raw message audit trail model."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RawMessage(Base):
    """Audit trail for incoming messages from Kraken."""

    __tablename__ = "raw_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(nullable=True, unique=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # text, image, audio
    content: Mapped[Optional[str]] = mapped_column(nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(nullable=True)
    received_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    intent: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    intent_conf: Mapped[Optional[Decimal]] = mapped_column(nullable=True)
    used_llm: Mapped[bool] = mapped_column(default=False)

    # Relationships
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="raw_message")

    def __repr__(self) -> str:
        return f"<RawMessage(id={self.id}, type={self.type}, user_id={self.user_id!r})>"


# Import here to avoid circular imports
from .expense import Expense  # noqa: E402
