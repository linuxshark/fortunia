"""Category model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Category(Base):
    """Financial expense category."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    keywords: Mapped[list[str]] = mapped_column(default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="category")
    merchants: Mapped[list["Merchant"]] = relationship("Merchant", back_populates="category")

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name!r})>"


# Import here to avoid circular imports
from .expense import Expense  # noqa: E402
from .merchant import Merchant  # noqa: E402
