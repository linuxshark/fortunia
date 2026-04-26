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

    # Handle standard number format: "15.000" (Chile) or "15000" (space-separated)
    # Also "15,50" (decimal) or "15.50"
    number_match = re.search(r'(\d{1,3}(?:\.\d{3})*|\d+)(?:[,.](\d{1,2}))?', text)
    if number_match:
        integer_part = number_match.group(1).replace('.', '')  # Remove thousand separators
        decimal_part = number_match.group(2) or ''

        if decimal_part:
            # If we have decimal, use comma or period appropriately
            amount_str = f"{integer_part}.{decimal_part}"
        else:
            amount_str = integer_part

        try:
            return Decimal(amount_str)
        except Exception:
            pass

    return None
