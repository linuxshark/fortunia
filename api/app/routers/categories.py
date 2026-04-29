"""Categories management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import verify_internal_key
from app.models.category import Category
from app.models.expense import Expense

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    name: str
    applicable_to: str = "expense"
    keywords: List[str] = []
    icon: Optional[str] = None
    color: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    applicable_to: str
    keywords: List[str]
    icon: Optional[str]
    color: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=List[CategoryOut])
async def list_categories(
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> List[Category]:
    return db.query(Category).order_by(Category.name).all()


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> Category:
    if payload.applicable_to not in ("expense", "income", "both"):
        raise HTTPException(status_code=422, detail="applicable_to debe ser expense, income o both")

    existing = db.query(Category).filter(Category.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ya existe una categoría con ese nombre")

    cat = Category(
        name=payload.name,
        applicable_to=payload.applicable_to,
        keywords=payload.keywords,
        icon=payload.icon,
        color=payload.color,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    x_internal_key: str = Depends(verify_internal_key),
) -> None:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    in_use = db.query(Expense).filter(Expense.category_id == category_id).first()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar: la categoría tiene transacciones asociadas",
        )

    db.delete(cat)
    db.commit()
