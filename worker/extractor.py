"""Core extraction orchestrator — reused by scan.py (CLI) and app.py (/ocr).

bytes -> preprocess -> barcode(TED) -> OCR(Tesseract) -> header+items ->
categorize -> validate -> result dict. Si la calidad es baja, escala a Gemini.
Pure of DB writes (persistence lives in db.persist).
"""
from __future__ import annotations

import hashlib

from barcode import decode_ted
from extract import extract_header, extract_line_items
from ocr import run_ocr
from preprocess import preprocess
from validate import validate


def _categorize(items: list[dict]) -> None:
    try:
        from categorize import categorize
    except Exception:
        return
    for it in items:
        try:
            cat_id, norm, source = categorize(it["raw_text"])
            it["category_id"] = cat_id
            if norm:  # keep OCR name when no alias match
                it["normalized_name"] = norm
            it["category_source"] = source
        except Exception:
            pass


def _needs_escalation(result: dict) -> bool:
    """True si Tesseract no extrajo suficiente información de calidad."""
    conf = result.get("ocr_confidence", 0)
    items = result.get("line_items", [])
    status = result.get("validation_status", "")
    # confianza baja → siempre escalar
    if conf < 65:
        return True
    # pocos ítems Y validación fallida → escalar
    if len(items) < 20 and status != "ok":
        return True
    return False


def _try_gemini(raw: bytes, source_image_path: str | None, fallback: dict) -> dict:
    """Intenta extracción con Gemini; si falla devuelve el resultado de Tesseract."""
    try:
        from config import settings
        if not settings.gemini_api_key:
            return fallback
        from gemini_ocr import gemini_extract
        return gemini_extract(raw, source_image_path)
    except Exception as exc:
        fallback.setdefault("problems", []).append(f"gemini_fallback_failed: {exc}")
        return fallback


def extract_from_bytes(raw: bytes, source_image_path: str | None = None) -> dict:
    sha = hashlib.sha256(raw).hexdigest()

    gray, binary = preprocess(raw)
    ted = decode_ted(gray)
    text, words, conf = run_ocr(binary)

    header = extract_header(text, ted)
    items = extract_line_items(text)
    _categorize(items)

    status, problems = validate(header, items)

    result = {
        **header,
        "image_sha256": sha,
        "source_image_path": source_image_path,
        "ocr_engine": "tesseract",
        "ocr_confidence": round(conf, 1),
        "ocr_raw_text": text,
        "line_items": items,
        "validation_status": status,
        "problems": problems,
        "ted_decoded": ted is not None,
    }

    if _needs_escalation(result):
        result = _try_gemini(raw, source_image_path, result)

    return result
