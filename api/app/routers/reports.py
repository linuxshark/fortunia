"""Reporting endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import verify_internal_key
from app.models import Category, Expense
from app.schemas.reports import (
    CategoryReportResponse,
    CategorySummary,
    DayReportResponse,
    MonthReportResponse,
    TopMerchantsResponse,
    TrendPoint,
    TrendReportResponse,
    MerchantSummary,
)

router = APIRouter(prefix="/reports", tags=["reports"])

SANTIAGO_TZ = ZoneInfo("America/Santiago")


def _now_santiago() -> datetime:
    return datetime.now(SANTIAGO_TZ)


@router.get("/today", response_model=DayReportResponse)
async def report_today(
    user_id: str = Query("user"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> DayReportResponse:
    """Get today's expense report (Santiago timezone)."""
    now = _now_santiago()
    today = now.date()
    start = datetime(today.year, today.month, today.day, tzinfo=SANTIAGO_TZ)
    end = start + timedelta(days=1)

    expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.spent_at >= start,
        Expense.spent_at < end,
    ).options(joinedload(Expense.category)).all()

    total = sum(e.amount for e in expenses) if expenses else Decimal("0")

    return DayReportResponse(
        date=today.isoformat(),
        total=total,
        currency="CLP",
        count=len(expenses),
        expenses=[{"id": e.id, "amount": float(e.amount)} for e in expenses],
    )


@router.get("/month", response_model=MonthReportResponse)
async def report_month(
    user_id: str = Query("user"),
    ym: str = Query(None, description="YYYY-MM format"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> MonthReportResponse:
    """Get monthly expense report."""
    now = _now_santiago()
    if ym:
        try:
            year, month = map(int, ym.split("-"))
        except (ValueError, IndexError):
            year, month = now.year, now.month
    else:
        year, month = now.year, now.month

    expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        func.extract("year", Expense.spent_at) == year,
        func.extract("month", Expense.spent_at) == month,
    ).options(joinedload(Expense.category)).all()

    total = sum(e.amount for e in expenses) if expenses else Decimal("0")

    by_category: dict = {}
    for exp in expenses:
        cat_name = exp.category.name if exp.category else "Otros"
        if cat_name not in by_category:
            by_category[cat_name] = {"count": 0, "total": Decimal("0")}
        by_category[cat_name]["count"] += 1
        by_category[cat_name]["total"] += exp.amount

    categories = [
        CategorySummary(
            category=cat,
            count=data["count"],
            total=data["total"],
            average=data["total"] / data["count"] if data["count"] > 0 else Decimal("0"),
            percentage=float(data["total"] / total * 100) if total > 0 else 0.0,
        )
        for cat, data in by_category.items()
    ]

    return MonthReportResponse(
        month=f"{year}-{month:02d}",
        total=total,
        currency="CLP",
        count=len(expenses),
        by_category=categories,
    )


@router.get("/categories", response_model=CategoryReportResponse)
async def report_categories(
    user_id: str = Query("user"),
    period: str = Query("month", description="month|year"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> CategoryReportResponse:
    """Get category breakdown report."""
    now = _now_santiago()

    if period == "month":
        start = datetime(now.year, now.month, 1, tzinfo=SANTIAGO_TZ)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1, tzinfo=SANTIAGO_TZ)
        else:
            end = datetime(now.year, now.month + 1, 1, tzinfo=SANTIAGO_TZ)
    else:  # year
        start = datetime(now.year, 1, 1, tzinfo=SANTIAGO_TZ)
        end = datetime(now.year + 1, 1, 1, tzinfo=SANTIAGO_TZ)

    expenses = db.query(Expense).filter(
        Expense.user_id == user_id,
        Expense.spent_at >= start,
        Expense.spent_at < end,
    ).options(joinedload(Expense.category)).all()

    total = sum(e.amount for e in expenses) if expenses else Decimal("0")

    by_category: dict = {}
    for exp in expenses:
        cat_name = exp.category.name if exp.category else "Otros"
        if cat_name not in by_category:
            by_category[cat_name] = {"count": 0, "total": Decimal("0")}
        by_category[cat_name]["count"] += 1
        by_category[cat_name]["total"] += exp.amount

    categories = [
        CategorySummary(
            category=cat,
            count=data["count"],
            total=data["total"],
            average=data["total"] / data["count"] if data["count"] > 0 else Decimal("0"),
            percentage=float(data["total"] / total * 100) if total > 0 else 0.0,
        )
        for cat, data in sorted(by_category.items(), key=lambda x: x[1]["total"], reverse=True)
    ]

    return CategoryReportResponse(
        period=period,
        categories=categories,
        total=total,
    )


@router.get("/top-merchants", response_model=TopMerchantsResponse)
async def report_top_merchants(
    user_id: str = Query("user"),
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> TopMerchantsResponse:
    """Get top merchants by spending."""
    return TopMerchantsResponse(
        limit=limit,
        merchants=[],
        total_expenses=0,
    )


@router.get("/trend", response_model=TrendReportResponse)
async def report_trend(
    user_id: str = Query("user"),
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> TrendReportResponse:
    """Get spending trend over last N months."""
    now = _now_santiago()
    trend = []
    total_amount = Decimal("0")

    for i in range(months, 0, -1):
        # Calculate month by proper month arithmetic, not timedelta
        month_offset = now.month - i
        year = now.year + (month_offset - 1) // 12
        month = ((month_offset - 1) % 12) + 1

        monthly_expenses = db.query(Expense).filter(
            Expense.user_id == user_id,
            func.extract("year", Expense.spent_at) == year,
            func.extract("month", Expense.spent_at) == month,
        ).all()

        monthly_total = sum(e.amount for e in monthly_expenses) if monthly_expenses else Decimal("0")
        total_amount += monthly_total

        trend.append(
            TrendPoint(
                month=f"{year}-{month:02d}",
                total=monthly_total,
                count=len(monthly_expenses),
            )
        )

    average = total_amount / months if months > 0 else Decimal("0")

    return TrendReportResponse(
        months=months,
        trend=trend,
        average_monthly=average,
    )
