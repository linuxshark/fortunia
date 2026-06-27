"""Core extraction orchestrator — reused by scan.py (CLI) and app.py (/ocr).

bytes -> preprocess -> barcode(TED) -> OCR(Tesseract) -> header+items ->
categorize -> validate -> result dict. Pure of DB writes (persistence lives in
db.persist). Categorization is best-effort and degrades if the DB is down.
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
            it["normalized_name"] = norm
            it["category_source"] = source
        except Exception:
            pass


def extract_from_bytes(raw: bytes, source_image_path: str | None = None) -> dict:
    sha = hashlib.sha256(raw).hexdigest()

    gray, binary = preprocess(raw)
    ted = decode_ted(gray)
    text, words, conf = run_ocr(binary)

    header = extract_header(text, ted)
    items = extract_line_items(text)
    _categorize(items)

    status, problems = validate(header, items)

    return {
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
