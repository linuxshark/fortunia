"""Merchant model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Merchant(Base):
    """Merchant/vendor information for fuzzy matching."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    normalized: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    rut: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="merchants")
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="merchant")

    def __repr__(self) -> str:
        return f"<Merchant(id={self.id}, name={self.name!r})>"


# Import here to avoid circular imports
from .category import Category  # noqa: E402
from .expense import Expense  # noqa: E402
