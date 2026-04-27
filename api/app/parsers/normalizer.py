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
