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
IVA_RE = re.compile(r"\bIVA\b\s*(?:19\s*%?)?\D*([\d.]{2,})", re.IGNORECASE)
# Scan full text for CLP-format amounts (dot thousands separators)
ALL_CLP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{3}){1,3})\b")
# 8+ consecutive digits = barcode; strip before item search
BARCODE_RE = re.compile(r"\b\d{8,}\b")
# Search (not match) for product name + price anywhere in a line
ITEM_SEARCH_RE = re.compile(
    r"(?P<name>[A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-záéíóúÁÉÍÓÚñÑ0-9\s\.\-\']{1,35}?)"
    r"\s+\$?\s*(?P<amount>(?:\d{1,3}[.,]){1,2}\d{3}|\d{4,6})",
    re.UNICODE,
)
SKIP_WORDS = (
    "TOTAL", "SUBTOTAL", "IVA", "NETO", "VUELTO", "EFECTIVO", "CAMBIO",
    "FOLIO", "RUT", "R.U.T", "S.I.I", "SII", "DESCUENTO", "PROPINA",
    "BOLETA", "FACTURA", "ELECTRONICA", "FECHA", "CAJA", "CAJERO",
    "CODIGO", "TICKET", "TARJETA", "PREPAG", "DEBIT", "CREDIT",
    "VENDEDOR", "SUCURSAL", "ATENCION", "CONICO",
    "SUC:", "SUC ", "JULIO", "DIEZ",  # address line filter
)


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
    totals = [t for t in totals if t and t > 100]

    # Fallback: scan whole text for CLP-format amounts; pick largest if TOTAL_RE missed
    all_clp = [clp_to_int(m) for m in ALL_CLP_RE.findall(text)]
    all_clp = [a for a in all_clp if a and a > 5_000]
    if all_clp:
        candidate = max(all_clp)
        # use fallback if TOTAL_RE found nothing plausible or candidate is much larger
        if not totals or candidate > max(totals) * 5:
            totals = [candidate]

    if totals and not h["total"]:
        h["total"] = max(totals)

    m = NETO_RE.search(text)
    if m:
        h["net"] = clp_to_int(m.group(1))
    m = IVA_RE.search(text)
    if m:
        h["tax"] = clp_to_int(m.group(1))
    return h


def extract_line_items(text: str) -> list[dict]:
    """Search each line for name+price; strip barcodes first to reduce noise."""
    items: list[dict] = []
    seen: set[tuple] = set()
    n = 0
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 5:
            continue
        upper = line.upper()
        if any(w in upper for w in SKIP_WORDS):
            continue
        # remove barcodes so regex doesn't anchor on them
        cleaned = BARCODE_RE.sub(" ", line).strip()
        if len(cleaned) < 4:
            continue
        m = ITEM_SEARCH_RE.search(cleaned)
        if not m:
            continue
        raw_amount_str = m.group("amount")
        amount = clp_to_int(raw_amount_str)
        name = m.group("name").strip()
        if amount is None or amount < 200 or amount > 300_000:
            continue
        if len(name) < 3:
            continue
        letter_count = sum(1 for c in name if c.isalpha())
        if letter_count < 3 or letter_count / max(len(name), 1) < 0.35:
            continue
        # require at least one word of 3+ consecutive letters (filters garbage like "ES iz")
        if not re.search(r'[A-Za-záéíóúÁÉÍÓÚñÑ]{3,}', name):
            continue
        key = (name[:15].upper(), amount)
        if key in seen:
            continue
        seen.add(key)
        n += 1
        items.append({
            "line_no": n,
            "raw_text": line[:100],
            "normalized_name": name[:50],
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
