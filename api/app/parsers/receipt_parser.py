"""Receipt/boleta parser for extracted OCR text."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .text_parser import ParsedExpense


def parse_receipt(ocr_text: str) -> ParsedExpense:
    """
    Parse receipt OCR text to extract expense data.

    Extracts:
    - Total amount (regex for TOTAL, TOTAL A PAGAR, etc.)
    - Merchant name (first non-empty line)
    - RUT (Chilean business ID)
    - Date (various formats)

    Args:
        ocr_text: Raw OCR output from Tesseract

    Returns:
        ParsedExpense with extracted data
    """
    result = ParsedExpense()

    if not ocr_text or not isinstance(ocr_text, str):
        return result

    text_upper = ocr_text.upper()
    lines = ocr_text.split("\n")

    # 1. Extract total amount — Chilean format: 15.000 means 15,000 (no cents)
    total_patterns = [
        r"TOTAL\s*A\s*PAGAR[:\s]*\$?\s*([\d.,]+)",
        r"MONTO\s*TOTAL[:\s]*\$?\s*([\d.,]+)",
        r"TOTAL[:\s]*\$?\s*([\d.,]+)",
    ]

    for pattern in total_patterns:
        match = re.search(pattern, text_upper)
        if match:
            raw = match.group(1)
            # Chilean format: dots as thousands separator, comma as decimal (rare for CLP)
            # Remove thousand-separator dots; if there's a trailing comma+digits treat as decimal
            if re.match(r"^\d{1,3}(\.\d{3})+$", raw):
                # Format like 15.000 or 1.500.000 — pure thousands separator
                amount_str = raw.replace(".", "")
            elif "," in raw:
                # e.g. 15.500,90 — dot=thousands, comma=decimal
                amount_str = raw.replace(".", "").replace(",", ".")
            else:
                amount_str = raw.replace(".", "").replace(",", "")

            try:
                result.amount = Decimal(amount_str)
                if result.amount > 0:
                    break
            except Exception:
                pass

    if not result.amount:
        # Fallback: look for any 4+ digit number (likely a CLP amount)
        numbers = re.findall(r"\b(\d{4,})\b", ocr_text)
        if numbers:
            try:
                result.amount = Decimal(numbers[0])
            except Exception:
                pass

    # 2. Extract merchant name (first meaningful line)
    for line in lines:
        line = line.strip()
        if line and len(line) > 3 and not re.match(r"^\d", line):
            result.merchant_hint = line[:60]
            break

    # 3. Extract RUT (Chilean format: XX.XXX.XXX-K)
    rut_pattern = r"(\d{1,2}\.\d{3}\.\d{3}-[0-9kK])"
    rut_match = re.search(rut_pattern, ocr_text)

    # 4. Extract date (for future use)
    date_patterns = [
        r"(\d{2}/\d{2}/\d{4})",
        r"(\d{2}-\d{2}-\d{4})",
        r"(\d{2}/\d{2}/\d{2})",
    ]
    for pattern in date_patterns:
        if re.search(pattern, ocr_text):
            break

    # 5. Infer category from merchant name
    if result.merchant_hint:
        category_keywords = {
            "Alimentación": ["jumbo", "lider", "líder", "unimarc", "tottus", "santa isabel", "super"],
            "Transporte": ["uber", "taxi", "metro"],
            "Salud": ["farmacia", "clinic", "cruz verde", "salcobrand"],
        }
        for category, keywords in category_keywords.items():
            if any(kw in result.merchant_hint.lower() for kw in keywords):
                result.category_hint = category
                break

    # 6. Calculate confidence
    confidence = 0.5
    if result.amount:
        confidence += 0.3
    if result.merchant_hint:
        confidence += 0.1
    if rut_match:
        confidence += 0.1

    result.confidence = min(confidence, 0.95)
    result.parse_method = "ocr"

    return result
