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
    - Merchant name (first 3 non-empty lines)
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

    text_lower = ocr_text.lower()
    lines = ocr_text.split("\n")

    # 1. Extract total amount
    total_patterns = [
        r"TOTAL\s*A\s*PAGAR[:\s]*(\d+[.,]\d+|\d+)",
        r"TOTAL\s*[:\s]*(\d+[.,]\d+|\d+)",
        r"MONTO\s*TOTAL[:\s]*(\d+[.,]\d+|\d+)",
        r"TOTAL[:\s]*(?:CLP\s*)?(\d+[.,]\d+|\d+)",
    ]

    for pattern in total_patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", ".").replace(".", "")
            try:
                result.amount = Decimal(amount_str) / 100  # Assume cents
                if result.amount > 100:  # Likely valid amount
                    break
            except Exception:
                pass

    if not result.amount:
        # Fallback: look for any large number
        numbers = re.findall(r"\d{4,}", ocr_text)
        if numbers:
            try:
                result.amount = Decimal(numbers[0])
            except Exception:
                pass

    # 2. Extract merchant name (first 3 non-empty lines)
    merchant_lines = []
    for line in lines:
        line = line.strip()
        if line and len(line) > 3:  # Skip short lines
            merchant_lines.append(line)
            if len(merchant_lines) >= 3:
                break

    if merchant_lines:
        result.merchant_hint = " ".join(merchant_lines[:1])

    # 3. Extract RUT (Chilean format: XX.XXX.XXX-K)
    rut_pattern = r"(\d{1,2}\.\d{3}\.\d{3}-[0-9kK])"
    rut_match = re.search(rut_pattern, ocr_text)
    if rut_match:
        # RUT found, could use for merchant lookup (v2)
        pass

    # 4. Extract date
    date_patterns = [
        r"(\d{2}/\d{2}/\d{4})",  # DD/MM/YYYY
        r"(\d{2}-\d{2}-\d{4})",  # DD-MM-YYYY
        r"(\d{2}/\d{2}/\d{2})",  # DD/MM/YY
    ]

    for pattern in date_patterns:
        date_match = re.search(pattern, ocr_text)
        if date_match:
            # Date found, could parse (v2)
            break

    # 5. Infer category from merchant name
    if result.merchant_hint:
        category_keywords = {
            "Alimentación": ["jumbo", "lider", "unimarc", "super"],
            "Transporte": ["uber", "taxi", "metro"],
            "Salud": ["farmacia", "clinic"],
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
