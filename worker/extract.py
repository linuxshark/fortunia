"""Extraction — regex header anchors (+ TED reconcile) and best-effort line items.

Header is robust (SII format is regular). Line items here are a SIMPLE
single-line heuristic for the MVP demo; the real positional/bbox reconstruction
is Phase 3 (see extract_line_items_positional stub). See docs/03 Stage 4.
"""
from __future__ import annotations

import re

from normalize import clp_to_int, parse_date, validate_rut

RUT_RE = re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b")
FOLIO_RE = re.compile(r"(?:FOLIO|N[º°o]?)\s*[:#]?\s*(\d{3,})", re.IGNORECASE)
TOTAL_RE = re.compile(r"\bTOTAL\b[^\d]*([\d.\s]{2,})", re.IGNORECASE)
NETO_RE = re.compile(r"\b(?:NETO|MONTO NETO)\b[^\d]*([\d.\s]{2,})", re.IGNORECASE)
# IVA line shows the 19% rate before the amount; skip the rate, grab the amount
IVA_RE = re.compile(r"\bIVA\b\s*(?:19\s*%?)?\D*([\d.]{2,})", re.IGNORECASE)
# line: "<name> .... <amount>"  amount = CLP integer with thousands dots
LINE_ITEM_RE = re.compile(r"^(?P<name>.+?\D)\s+\$?\s*(?P<amount>\d{1,3}(?:\.\d{3})+|\d{3,6})\s*$")
SKIP_WORDS = ("TOTAL", "SUBTOTAL", "IVA", "NETO", "VUELTO", "EFECTIVO", "CAMBIO",
              "FOLIO", "RUT", "R.U.T", "S.I.I", "SII", "DESCUENTO", "PROPINA",
              "BOLETA", "FACTURA", "ELECTRONICA", "FECHA", "CAJA", "CAJERO")


def _first_valid_rut(text: str) -> str | None:
    for m in RUT_RE.findall(text):
        if validate_rut(m):
            return m
    return None


def extract_header(text: str, ted=None) -> dict:
    h: dict = {
        "rut_emisor": None, "rut_receptor": None, "tipo_dte": None, "doc_type": None,
        "folio": None, "issued_date": None, "merchant_name": None,
        "net": None, "tax": None, "total": None, "ted_total": None,
        "header_source": "ocr",
    }

    # --- TED first (verified) ---
    if ted is not None:
        h["header_source"] = "ted"
        h["rut_emisor"] = ted.rut_emisor
        h["rut_receptor"] = ted.rut_receptor
        h["tipo_dte"] = ted.tipo_dte
        h["folio"] = ted.folio
        h["merchant_name"] = ted.merchant_name
        h["ted_total"] = ted.total
        h["total"] = ted.total
        if ted.issued_date:
            h["issued_date"] = parse_date(ted.issued_date)
        if ted.tipo_dte in (39, 41):
            h["doc_type"] = "boleta"
        elif ted.tipo_dte in (33, 34):
            h["doc_type"] = "factura"

    # --- OCR fallback / fill gaps ---
    if not h["rut_emisor"]:
        h["rut_emisor"] = _first_valid_rut(text)
    if not h["folio"]:
        m = FOLIO_RE.search(text)
        if m:
            h["folio"] = m.group(1)
    if not h["issued_date"]:
        h["issued_date"] = parse_date(text)

    totals = [clp_to_int(x) for x in TOTAL_RE.findall(text)]
    totals = [t for t in totals if t]
    if totals and not h["total"]:
        h["total"] = max(totals)            # grand total = largest TOTAL line
    m = NETO_RE.search(text)
    if m:
        h["net"] = clp_to_int(m.group(1))
    m = IVA_RE.search(text)
    if m:
        h["tax"] = clp_to_int(m.group(1))
    return h


def extract_line_items(text: str) -> list[dict]:
    """MVP single-line heuristic: name + trailing amount as line_total."""
    items: list[dict] = []
    n = 0
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 4:
            continue
        if any(w in line.upper() for w in SKIP_WORDS):
            continue
        m = LINE_ITEM_RE.match(line)
        if not m:
            continue
        amount = clp_to_int(m.group("amount"))
        name = m.group("name").strip()
        if amount is None or amount <= 0 or len(name) < 2:
            continue
        n += 1
        items.append({
            "line_no": n,
            "raw_text": line,
            "normalized_name": None,
            "category_id": None,
            "category_source": "unmatched",
            "qty": 1,
            "unit_price": amount,
            "line_total": amount,
        })
    return items


def extract_line_items_positional(words: list) -> list[dict]:
    """Phase 3: cluster word boxes into rows by y, infer columns by x,
    map name | qty | unit_price | line_total. Not in MVP."""
    raise NotImplementedError("Phase 3 — positional reconstruction")
