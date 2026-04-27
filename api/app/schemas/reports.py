"""Pydantic schemas for reports."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class CategorySummary(BaseModel):
    """Category summary for reports."""

    category: str
    count: int
    total: Decimal
    average: Decimal
    percentage: float = 0.0


class MerchantSummary(BaseModel):
    """Merchant summary."""

    merchant: str
    count: int
    total: Decimal


class TrendPoint(BaseModel):
    """Single point in a trend."""

    month: str
    total: Decimal
    count: int


class DayReportResponse(BaseModel):
    """Daily report."""

    date: str
    total: Decimal
    currency: str
    count: int
    expenses: list[dict] = []


class MonthReportResponse(BaseModel):
    """Monthly report."""

    month: str
    total: Decimal
    currency: str
    count: int
    by_category: list[CategorySummary]


class CategoryReportResponse(BaseModel):
    """Category breakdown report."""

    period: str
    categories: list[CategorySummary]
    total: Decimal


class TopMerchantsResponse(BaseModel):
    """Top merchants report."""

    limit: int
    merchants: list[MerchantSummary]
    total_expenses: int


class TrendReportResponse(BaseModel):
    """Trend report (last N months)."""

    months: int
    trend: list[TrendPoint]
    average_monthly: Decimal


class ExportRequest(BaseModel):
    """Export request."""

    format: str = Field(..., description="csv|xlsx")
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CategoryBalanceSummary(BaseModel):
    """Category entry in monthly balance."""

    category: str
    type: str  # "expense" | "income"
    total: Decimal
    count: int


class MonthlyBalanceResponse(BaseModel):
    """Monthly income vs expense balance."""

    month: str
    user_id: str
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    by_category: list[CategoryBalanceSummary]


class UserItem(BaseModel):
    """User entry for filter dropdown."""

    user_key: str
    display_name: str