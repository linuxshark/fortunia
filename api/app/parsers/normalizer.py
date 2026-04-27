"""Amount normalization — convert text variations to decimal."""

import re
from decimal import Decimal
from typing import Optional


def normalize_amount(text: str) -> Optional[Decimal]:
    """
    Extract and normalize monetary amount from text.

    Examples:
        "gasté 15 lucas" → Decimal('15000')
        "pagué 15k" → Decimal('15000')
        "compré por 15 mil" → Decimal('15000')
        "cuesta 15.000" → Decimal('15000')
        "costó 15,50" → Decimal('15.50')
        "1.5 millones" → Decimal('1500000')
        "$15.000" → Decimal('15000')
    """
    if not text or not isinstance(text, str):
        return None

    text = text.lower().strip()

    # Remove currency symbols
    text = re.sub(r'[$€¥]', '', text)

    # Convert Spanish word-numbers to digits (for audio transcripts)
    WORD_NUMBERS = {
        "cero": 0, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
        "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
        "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
        "dieciséis": 16, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
        "veinte": 20, "veintiuno": 21, "veintidós": 22, "veintidos": 22, "veintitrés": 23,
        "veintitrés": 23, "veinticuatro": 24, "veinticinco": 25,
        "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60,
        "setenta": 70, "ochenta": 80, "noventa": 90,
        "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300,
        "cuatrocientos": 400, "quinientos": 500, "seiscientos": 600,
        "setecientos": 700, "ochocientos": 800, "novecientos": 900,
    }
    # Replace word-number + "mil" patterns (e.g. "quince mil" → "15000", "cinco mil" → "5000")
    for word, value in WORD_NUMBERS.items():
        # word + mil
        text = re.sub(
            r'\b' + re.escape(word) + r'\s+mil\b',
            str(value * 1000),
            text
        )
    # Replace standalone word-numbers (e.g. "quince" → "15")
    for word, value in WORD_NUMBERS.items():
        text = re.sub(r'\b' + re.escape(word) + r'\b', str(value), text)

    # Handle "lucas" (slang for 1000s in Chile)
    lucas_match = re.search(r'(\d+(?:[.,]\d+)?)\s*lucas', text)
    if lucas_match:
        amount_str = lucas_match.group(1).replace(',', '.')
        try:
            return Decimal(amount_str) * 1000
        except Exception:
            pass

    # Handle "millones" (millions)
    millones_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:millones?)', text)
    if millones_match:
        amount_str = millones_match.group(1).replace(',', '.')
        try:
            return Decimal(amount_str) * 1_000_000
        except Exception:
            pass

    # Handle "mil" (thousand)
    mil_match = re.search(r'(\d+(?:[.,]\d+)?)\s*mil(?:es)?', text)
    if mil_match:
        amount_str = mil_match.group(1).replace(',', '.')
        try:
            return Decimal(amount_str) * 1000
        except Exception:
            pass

    # Handle "k" or "K" (thousand)
    k_match = re.search(r'(\d+(?:[.,]\d+)?)\s*[kK](?:\s|$)', text)
    if k_match:
        amount_str = k_match.group(1).replace(',', '.')
        try:
            return Decimal(amount_str) * 1000
        except Exception:
            pass

    # Handle "m" or "M" (million) — be careful not to confuse with other letters
    m_match = re.search(r'(\d+(?:[.,]\d+)?)\s*[mM](?:\s|$)', text)
    if m_match:
        # Only treat as million if preceded by whitespace
        amount_str = m_match.group(1).replace(',', '.')
        try:
            return Decimal(amount_str) * 1_000_000
        except Exception:
            pass

    # Try Chilean format first: digits with dots as thousand separators (e.g. "15.000", "1.500.000")
    # Requires at least one .NNN group to distinguish from decimal numbers
    chilean_match = re.search(r'(\d{1,3}(?:\.\d{3})+)', text)
    if chilean_match:
        integer_part = chilean_match.group(1).replace('.', '')
        try:
            return Decimal(integer_part)
        except Exception:
            pass

    # Decimal number with comma separator (e.g. "15,50" → 15.50, NOT thousands)
    # Only when decimal part is 1-2 digits (not 3, which would be thousands)
    decimal_comma_match = re.search(r'\b(\d+),(\d{1,2})\b', text)
    if decimal_comma_match:
        try:
            return Decimal(f"{decimal_comma_match.group(1)}.{decimal_comma_match.group(2)}")
        except Exception:
            pass

    # Decimal number with period separator (e.g. "15.50") — only 1-2 decimal digits
    decimal_period_match = re.search(r'\b(\d+)\.(\d{1,2})\b', text)
    if decimal_period_match:
        try:
            return Decimal(f"{decimal_period_match.group(1)}.{decimal_period_match.group(2)}")
        except Exception:
            pass

    # Plain integer (e.g. "4000000", "6500", "18000")
    plain_match = re.search(r'\b(\d{3,})\b', text)
    if plain_match:
        try:
            return Decimal(plain_match.group(1))
        except Exception:
            pass

    # Small numbers (1-2 digit, e.g. amounts like "50")
    small_match = re.search(r'\b(\d{1,2})\b', text)
    if small_match:
        try:
            return Decimal(small_match.group(1))
        except Exception:
            pass

    return None
