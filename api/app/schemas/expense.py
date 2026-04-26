"""Pydantic schemas for expenses."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    """Create expense request."""

    amount: Decimal = Field(..., gt=0)
    currency: str = "CLP"
    category_id: Optional[int] = None
    merchant_id: Optional[int] = None
    spent_at: Optional[datetime] = None
    note: Optional[str] = None
    source: str = "text"


class ExpenseUpdate(BaseModel):
    """Update expense request."""

    amount: Optional[Decimal] = None
    category_id: Optional[int] = None
    merchant_id: Optional[int] = None
    note: Optional[str] = None


class ExpenseResponse(BaseModel):
    """Expense response."""

    id: int
    user_id: str
    amount: Decimal
    currency: str
    category_id: Optional[int] = None
    merchant_id: Optional[int] = None
    spent_at: datetime
    note: Optional[str] = None
    source: str
    confidence: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IngestResponse(BaseModel):
    """Response for /ingest/* endpoints."""

    status: str = Field(..., description="registered|needs_confirmation|rejected")
    expense_id: Optional[int] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    merchant: Optional[str] = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    user_message: str = Field(..., description="Ready for Telegram")
    parse_method: str = "rules"


class IntentCheckRequest(BaseModel):
    """Request for /intent/check endpoint."""

    text: str


class IntentCheckResponse(BaseModel):
    """Response for /intent/check endpoint."""

    is_finance: bool
    confidence: float
    needs_llm: bool = False
    reason: str = ""
