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
from app.models.user import User as UserModel
from app.schemas.reports import (
    CategoryBalanceSummary,
    CategoryReportResponse,
    CategorySummary,
    DayReportResponse,
    MonthlyBalanceResponse,
    MonthReportResponse,
    TopMerchantsResponse,
    TrendPoint,
    TrendReportResponse,
    MerchantSummary,
    UserItem,
)

router = APIRouter(prefix="/reports", tags=["reports"])

SANTIAGO_TZ = ZoneInfo("America/Santiago")


def _now_santiago() -> datetime:
    return datetime.now(SANTIAGO_TZ)


@router.get("/today", response_model=DayReportResponse)
async def report_today(
    user_id: str = Query("all"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> DayReportResponse:
    """Get today's expense report (Santiago timezone)."""
    now = _now_santiago()
    today = now.date()
    start = datetime(today.year, today.month, today.day, tzinfo=SANTIAGO_TZ)
    end = start + timedelta(days=1)

    query = db.query(Expense).filter(
        Expense.spent_at >= start,
        Expense.spent_at < end,
    )
    if user_id != "all":
        query = query.filter(Expense.user_id == user_id)
    expenses = query.options(joinedload(Expense.category)).all()

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
    user_id: str = Query("all"),
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

    query = db.query(Expense).filter(
        func.extract("year", Expense.spent_at) == year,
        func.extract("month", Expense.spent_at) == month,
    )
    if user_id != "all":
        query = query.filter(Expense.user_id == user_id)
    expenses = query.options(joinedload(Expense.category)).all()

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
    user_id: str = Query("all"),
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

    query = db.query(Expense).filter(
        Expense.spent_at >= start,
        Expense.spent_at < end,
    )
    if user_id != "all":
        query = query.filter(Expense.user_id == user_id)
    expenses = query.options(joinedload(Expense.category)).all()

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
    user_id: str = Query("all"),
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

        month_query = db.query(Expense).filter(
            func.extract("year", Expense.spent_at) == year,
            func.extract("month", Expense.spent_at) == month,
        )
        if user_id != "all":
            month_query = month_query.filter(Expense.user_id == user_id)
        monthly_expenses = month_query.all()

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


@router.get("/monthly-balance", response_model=MonthlyBalanceResponse)
async def monthly_balance(
    user_id: str = Query("all", description="user_key or 'all' for family total"),
    month: str = Query(None, description="YYYY-MM format, defaults to current month"),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> MonthlyBalanceResponse:
    """Income vs expense balance for a given month."""
    now = _now_santiago()
    if month:
        try:
            year, m = map(int, month.split("-"))
        except (ValueError, IndexError):
            year, m = now.year, now.month
    else:
        year, m = now.year, now.month

    start = datetime(year, m, 1, tzinfo=SANTIAGO_TZ)
    if m == 12:
        end = datetime(year + 1, 1, 1, tzinfo=SANTIAGO_TZ)
    else:
        end = datetime(year, m + 1, 1, tzinfo=SANTIAGO_TZ)

    query = db.query(Expense).filter(
        Expense.spent_at >= start,
        Expense.spent_at < end,
    )
    if user_id != "all":
        query = query.filter(Expense.user_id == user_id)

    expenses = query.options(joinedload(Expense.category)).all()

    total_income = sum(e.amount for e in expenses if e.type == "income") or Decimal("0")
    total_exp = sum(e.amount for e in expenses if e.type == "expense") or Decimal("0")

    cat_totals: dict[tuple[str, str], dict] = {}
    for e in expenses:
        cat_name = e.category.name if e.category else "Otros"
        key = (cat_name, e.type)
        if key not in cat_totals:
            cat_totals[key] = {"total": Decimal("0"), "count": 0}
        cat_totals[key]["total"] += e.amount
        cat_totals[key]["count"] += 1

    by_category = [
        CategoryBalanceSummary(
            category=cat,
            type=typ,
            total=data["total"],
            count=data["count"],
        )
        for (cat, typ), data in sorted(cat_totals.items())
    ]

    ym_str = f"{year}-{m:02d}"
    return MonthlyBalanceResponse(
        month=ym_str,
        user_id=user_id,
        total_income=total_income,
        total_expenses=total_exp,
        balance=total_income - total_exp,
        by_category=by_category,
    )


@router.get("/users", response_model=list[UserItem])
async def list_users(
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> list[UserItem]:
    """Return users that have expenses, using display name from users table when available."""
    from sqlalchemy import distinct
    from app.models.expense import Expense as ExpenseModel

    # All user_ids that have at least one expense
    rows = db.query(distinct(ExpenseModel.user_id)).order_by(ExpenseModel.user_id).all()
    active_user_ids = [r[0] for r in rows]

    # Build display name map from users table (best-effort, may not exist)
    name_map: dict[str, str] = {}
    try:
        db_users = db.query(UserModel).filter(
            UserModel.user_key.in_(active_user_ids)
        ).all()
        name_map = {u.user_key: u.display_name for u in db_users}
    except Exception:
        pass

    result = [UserItem(user_key="all", display_name="Todos")]
    for uid in active_user_ids:
        result.append(UserItem(
            user_key=uid,
            display_name=name_map.get(uid, uid),  # fallback: mostrar el ID
        ))
    return result
