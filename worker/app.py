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
from admin import router as admin_router
from categorize import categorize, categorize_income, categorize_shared, resolve_shared
from intent import classify
from text_income import parse_income
from config import settings
from extractor import extract_from_bytes
from text_expense import ParseError, parse_expense

app = FastAPI(title="fortunia-worker", version="0.3.0")
app.include_router(admin_router)


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

    # ¿Es un gasto COMPARTIDO del hogar (ej. supermercado→Alimentos)? Se marca la
    # boleta y, tras persistir, se genera un pago del Fondo Común vinculado a ella.
    fund_cat_id = _resolve_fund_category(result)
    result["fund_category_id"] = fund_cat_id

    receipt_id, created = db.persist(result)

    routed_to_fund = False
    total = result.get("total")
    if created and fund_cat_id is not None and total and total > 0:
        month = (result.get("issued_date") or date.today()).replace(day=1)
        db.upsert_fund_payment(
            fund_cat_id, month, int(total), "ocr",
            result.get("merchant_name"), receipt_id=receipt_id,
        )
        routed_to_fund = True

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
        "routed_to_fund": routed_to_fund,
        "fund_category_id": fund_cat_id,
    }


def _resolve_fund_category(result: dict) -> int | None:
    """Mapea una boleta OCR a una categoría compartida del Fondo Común, o None.

    1) Categoría que Gemini asignó a la boleta ('household_category') → id shared.
    2) Fallback determinista: nombre del COMERCIO contra aliases compartidos
       (solo el comercio, no el texto de ítems, para evitar falsos positivos como
       un producto 'agua' que rutearía a la cuenta de Agua)."""
    cid = db.shared_category_id_by_name(result.get("fund_category"))
    if cid is not None:
        return cid
    cid, _, _ = categorize_shared(result.get("merchant_name") or "")
    return cid


def _register_expense(text: str) -> dict:
    """Parsea texto como gasto y lo persiste como recibo manual. Lanza ParseError."""
    parsed = parse_expense(text)
    amount = parsed["amount"]

    # 1) ¿Es un gasto COMPARTIDO del hogar? -> ruta al Fondo Común (no crea receipt).
    shared_id, shared_norm, shared_src = resolve_shared(parsed["category_text"])
    if shared_id is not None:
        month = date.today().replace(day=1)
        detail = parsed.get("detail")
        paid, remaining = db.upsert_fund_payment(shared_id, month, amount, "telegram", detail)
        return {
            "status": "stored",
            "routed_to": "fund",
            "amount": amount,
            "category_id": shared_id,
            "category": shared_norm or parsed["category_text"],
            "category_source": shared_src,
            "detail": detail,
            "month": str(month),
            "paid_amount": float(paid),
            "remaining": float(remaining),
        }

    # 2) Gasto normal -> flujo de boleta de texto (receipt + 1 line_item).
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
        "image_sha256": None,
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
        "routed_to": "expense",
        "receipt_id": receipt_id,
        "amount": amount,
        "category_text": parsed["category_text"],
        "category_id": cat_id,
        "category": norm or parsed["category_text"],
        "category_source": source,
        "issued_date": str(result["issued_date"]),
    }


def _register_income(text: str) -> dict:
    """Parsea texto como ingreso y lo persiste en la tabla incomes. Lanza ParseError."""
    parsed = parse_income(text)
    # Pass full raw text — verb-based aliases (vendí, sueldo) need it
    cat_id, norm, source = categorize_income(parsed["raw"])
    income_id, _ = db.persist_income(parsed, cat_id)
    return {
        "status": "stored",
        "kind": "income",
        "income_id": income_id,
        "amount": parsed["amount"],
        "source_text": parsed["source_text"],
        "category_id": cat_id,
        "category": norm or parsed["source_text"],
        "category_source": source,
        "issued_date": str(date.today()),
    }


@app.post("/text")
def text_entry(payload: TextExpense) -> dict:
    """Punto de entrada único para texto libre desde Telegram (openclaw).

    Clasifica la intención (ingreso vs gasto) y enruta al flujo correcto:
    "cobré mi sueldo 4.404.000" → ingreso; "gasté 40.000 en bencina" → gasto.
    """
    try:
        if classify(payload.text) == "income":
            return _register_income(payload.text)
        return {"kind": "expense", **_register_expense(payload.text)}
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class TextIncome(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


@app.post("/income")
def income_text(payload: TextIncome) -> dict:
    """Registra ingreso desde texto libre, forzando el flujo de ingreso."""
    try:
        return _register_income(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
