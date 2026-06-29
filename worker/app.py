"""FastAPI OCR worker (containerized, Tesseract). openclaw POSTs the photo here.

Run (compose):  uvicorn app:app --host 0.0.0.0 --port 8000
Flow: receive image -> store -> extract_from_bytes -> persist -> JSON summary.
"""
from __future__ import annotations

import hashlib

from fastapi import FastAPI, File, UploadFile

import db
from config import settings
from extractor import extract_from_bytes

app = FastAPI(title="fortunia-worker", version="0.2.0")


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
