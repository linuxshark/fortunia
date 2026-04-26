"""Attachment model for files (images, audio)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Attachment(Base):
    """File attachment (image, audio, etc.)."""

    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="attachment")

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, filename={self.filename!r})>"


# Import here to avoid circular imports
from .expense import Expense  # noqa: E402
