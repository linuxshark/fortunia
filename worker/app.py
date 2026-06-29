"""FastAPI OCR worker (containerized, Tesseract). openclaw POSTs the photo here.

Run (compose):  uvicorn app:app --host 0.0.0.0 --port 8000
Flow: receive image -> store -> extract_from_bytes -> persist -> JSON summary.
"""
from __future__ import annotations

import hashlib
from datetime import date

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

import db
from categorize import categorize, categorize_income
from text_income import parse_income
from config import settings
from extractor import extract_from_bytes
from text_expense import ParseError, parse_expense

app = FastAPI(title="fortunia-worker", version="0.3.0")


class TextExpense(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "db": db.healthy()}


@app.post("/ocr")
async def ocr(image: UploadFile = File(...)) -> dict:
    raw = await image.read()
    sha = hashlib.sha256(raw).hexdigest()

    # keep the original bytes (idempotent by hash)
    path = settings.image_dir / f"{sha}.bin"
    if not path.exists():
        path.write_bytes(raw)

    result = extract_from_bytes(raw, source_image_path=str(path))
    receipt_id, created = db.persist(result)

    return {
        "status": "stored" if created else "duplicate",
        "receipt_id": receipt_id,
        "sha256": sha,
        "header_source": result["header_source"],
        "ted_decoded": result["ted_decoded"],
        "merchant": result.get("merchant_name"),
        "rut_emisor": result.get("rut_emisor"),
        "folio": result.get("folio"),
        "issued_date": str(result.get("issued_date")) if result.get("issued_date") else None,
        "total": result.get("total"),
        "items": len(result["line_items"]),
        "validation_status": result["validation_status"],
        "problems": result["problems"],
    }


@app.post("/text")
def text_expense(payload: TextExpense) -> dict:
    """Registra un gasto a partir de texto libre ("gaste 40.000 en bencina").

    No pasa por OCR: parsea monto + categoría, mapea la categoría vía
    item_aliases y persiste un recibo manual con un único line_item.
    """
    try:
        parsed = parse_expense(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    amount = parsed["amount"]
    cat_id, norm, source = categorize(parsed["category_text"])

    result = {
        "merchant_name": None,
        "rut_emisor": None,
        "rut_receptor": None,
        "doc_type": "texto",
        "tipo_dte": None,
        "folio": None,
        "issued_date": date.today(),
        "net": None,
        "tax": None,
        "total": amount,
        "ted_total": None,
        "header_source": "texto",
        "validation_status": "ok",
        "source_image_path": None,
        "image_sha256": None,          # sin imagen: NULL no colisiona en el índice único
        "ocr_engine": "text",
        "ocr_confidence": None,
        "ocr_raw_text": parsed["raw"],
        "line_items": [
            {
                "line_no": 1,
                "raw_text": parsed["category_text"],
                "normalized_name": norm or parsed["category_text"],
                "category_id": cat_id,
                "category_source": source,
                "qty": 1,
                "unit_price": amount,
                "line_total": amount,
            }
        ],
    }

    receipt_id, created = db.persist(result)
    return {
        "status": "stored" if created else "duplicate",
        "receipt_id": receipt_id,
        "amount": amount,
        "category_text": parsed["category_text"],
        "category_id": cat_id,
        "category": norm or parsed["category_text"],
        "category_source": source,
        "issued_date": str(result["issued_date"]),
    }


class TextIncome(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


@app.post("/income")
def income_text(payload: TextIncome) -> dict:
    """Registra ingreso desde texto libre ("cobré 5.000.000 de sueldo").

    Parsea monto + fuente, categoriza contra aliases de ingresos,
    persiste en tabla incomes. Sin paso por OCR.
    """
    try:
        parsed = parse_income(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Pass full raw text — verb-based aliases (vendí, sueldo) need it
    cat_id, norm, source = categorize_income(parsed["raw"])
    income_id, _ = db.persist_income(parsed, cat_id)
    return {
        "status": "stored",
        "income_id": income_id,
        "amount": parsed["amount"],
        "source_text": parsed["source_text"],
        "category_id": cat_id,
        "category": norm or parsed["source_text"],
        "category_source": source,
        "issued_date": str(date.today()),
    }
