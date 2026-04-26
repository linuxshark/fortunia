"""Expense model."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Expense(Base):
    """Financial expense record."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="CLP", nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    merchant_id: Mapped[Optional[int]] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    spent_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    note: Mapped[Optional[str]] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # text, image, audio, manual
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    raw_msg_id: Mapped[Optional[int]] = mapped_column(ForeignKey("raw_messages.id"), nullable=True)
    attachment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("attachments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="expenses")
    merchant: Mapped[Optional["Merchant"]] = relationship("Merchant", back_populates="expenses")
    raw_message: Mapped[Optional["RawMessage"]] = relationship("RawMessage", back_populates="expenses")
    attachment: Mapped[Optional["Attachment"]] = relationship("Attachment", back_populates="expenses")

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, amount={self.amount}, currency={self.currency})>"


# Import here to avoid circular imports
from .attachment import Attachment  # noqa: E402
from .category import Category  # noqa: E402
from .merchant import Merchant  # noqa: E402
from .raw_message import RawMessage  # noqa: E402
