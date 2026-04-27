"""Expense CRUD endpoints."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import verify_internal_key
from app.models import Expense
from app.schemas.expense import ExpenseResponse, ExpenseCreate, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _to_response(e: Expense) -> ExpenseResponse:
    """Convert ORM Expense to ExpenseResponse including joined names."""
    return ExpenseResponse(
        id=e.id,
        user_id=e.user_id,
        amount=e.amount,
        currency=e.currency,
        category_id=e.category_id,
        category_name=e.category.name if e.category else None,
        merchant_id=e.merchant_id,
        merchant_name=e.merchant.name if e.merchant else None,
        spent_at=e.spent_at,
        note=e.note,
        source=e.source,
        confidence=e.confidence,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    user_id: str = Query("user"),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> list[ExpenseResponse]:
    """List expenses with optional filters."""
    query = (
        db.query(Expense)
        .options(joinedload(Expense.category), joinedload(Expense.merchant))
        .filter_by(user_id=user_id)
    )

    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date)
            query = query.filter(Expense.spent_at >= from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date)
            query = query.filter(Expense.spent_at <= to_dt)
        except ValueError:
            pass

    if category_id:
        query = query.filter_by(category_id=category_id)

    expenses = query.order_by(Expense.spent_at.desc()).limit(limit).offset(offset).all()
    return [_to_response(e) for e in expenses]


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> ExpenseResponse:
    """Get single expense."""
    expense = (
        db.query(Expense)
        .options(joinedload(Expense.category), joinedload(Expense.merchant))
        .filter_by(id=expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return _to_response(expense)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: int,
    data: ExpenseUpdate,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> ExpenseResponse:
    """Update expense."""
    expense = (
        db.query(Expense)
        .options(joinedload(Expense.category), joinedload(Expense.merchant))
        .filter_by(id=expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    if data.amount is not None:
        expense.amount = data.amount
    if data.category_id is not None:
        expense.category_id = data.category_id
    if data.merchant_id is not None:
        expense.merchant_id = data.merchant_id
    if data.note is not None:
        expense.note = data.note

    expense.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(expense)
    return _to_response(expense)


@router.delete("/{expense_id}")
async def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> dict:
    """Delete expense."""
    expense = db.query(Expense).filter_by(id=expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    db.commit()
    return {"status": "deleted", "id": expense_id}
