"""Router admin: list/edit/soft-delete/restore de transacciones ya persistidas.

Sin autenticación (igual que el resto del worker): solo alcanzable en la red
local del Mac mini. Ver docs/superpowers/specs/2026-07-11-admin-crud-design.md.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import admin_db

router = APIRouter(prefix="/admin", tags=["admin"])


class ReceiptUpdate(BaseModel):
    total: float | None = None
    issued_date: date | None = None


class LineItemUpdate(BaseModel):
    unit_price: float | None = None
    qty: float | None = None
    line_total: float | None = None
    category_id: int | None = None


class IncomeUpdate(BaseModel):
    amount: float | None = None
    category_id: int | None = None
    issued_date: date | None = None
    raw_text: str | None = None


class FundPaymentUpdate(BaseModel):
    amount: float | None = None
    category_id: int | None = None
    month: date | None = None
    detail: str | None = None


def _or_404(row: dict | None) -> dict:
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return row


@router.get("/categories")
def list_categories() -> list[dict]:
    return admin_db.list_categories()


@router.get("/receipts")
def list_receipts(month: str | None = None) -> list[dict]:
    return admin_db.list_receipts(month)


@router.get("/receipts/{receipt_id}/items")
def list_receipt_items(receipt_id: int) -> list[dict]:
    return admin_db.list_receipt_items(receipt_id)


@router.patch("/receipts/{receipt_id}")
def update_receipt(receipt_id: int, payload: ReceiptUpdate) -> dict:
    return _or_404(admin_db.update_receipt(receipt_id, payload.total, payload.issued_date))


@router.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: int) -> dict:
    return _or_404(admin_db.soft_delete_receipt(receipt_id))


@router.post("/receipts/{receipt_id}/restore")
def restore_receipt(receipt_id: int) -> dict:
    return _or_404(admin_db.restore_receipt(receipt_id))


@router.patch("/line-items/{item_id}")
def update_line_item(item_id: int, payload: LineItemUpdate) -> dict:
    return _or_404(admin_db.update_line_item(
        item_id, payload.unit_price, payload.qty, payload.line_total, payload.category_id
    ))


@router.delete("/line-items/{item_id}")
def delete_line_item(item_id: int) -> dict:
    return _or_404(admin_db.soft_delete_line_item(item_id))


@router.post("/line-items/{item_id}/restore")
def restore_line_item(item_id: int) -> dict:
    return _or_404(admin_db.restore_line_item(item_id))


@router.get("/incomes")
def list_incomes(month: str | None = None) -> list[dict]:
    return admin_db.list_incomes(month)


@router.patch("/incomes/{income_id}")
def update_income(income_id: int, payload: IncomeUpdate) -> dict:
    return _or_404(admin_db.update_income(
        income_id, payload.amount, payload.category_id, payload.issued_date, payload.raw_text
    ))


@router.delete("/incomes/{income_id}")
def delete_income(income_id: int) -> dict:
    return _or_404(admin_db.soft_delete_income(income_id))


@router.post("/incomes/{income_id}/restore")
def restore_income(income_id: int) -> dict:
    return _or_404(admin_db.restore_income(income_id))


@router.get("/fund-payments")
def list_fund_payments(month: str | None = None) -> list[dict]:
    return admin_db.list_fund_payments(month)


@router.patch("/fund-payments/{payment_id}")
def update_fund_payment(payment_id: int, payload: FundPaymentUpdate) -> dict:
    return _or_404(admin_db.update_fund_payment(
        payment_id, payload.amount, payload.category_id, payload.month, payload.detail
    ))


@router.delete("/fund-payments/{payment_id}")
def delete_fund_payment(payment_id: int) -> dict:
    return _or_404(admin_db.soft_delete_fund_payment(payment_id))


@router.post("/fund-payments/{payment_id}/restore")
def restore_fund_payment(payment_id: int) -> dict:
    return _or_404(admin_db.restore_fund_payment(payment_id))
