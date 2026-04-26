"""Text-based expense parser."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .normalizer import normalize_amount


@dataclass
class ParsedExpense:
    """Result of parsing an expense text."""

    amount: Optional[Decimal] = None
    currency: str = "CLP"
    category_hint: Optional[str] = None
    merchant_hint: Optional[str] = None
    note: Optional[str] = None
    confidence: float = 0.0
    parse_method: str = "rules"  # "rules", "llm", "hybrid"


def parse_expense_text(text: str) -> ParsedExpense:
    """
    Parse expense from free-form text.

    Example:
        "gasté 15 lucas en comida en Jumbo" →
        ParsedExpense(
            amount=Decimal('15000'),
            currency='CLP',
            category_hint='Alimentación',
            merchant_hint='Jumbo',
            confidence=0.9
        )
    """
    result = ParsedExpense()

    if not text or not isinstance(text, str):
        return result

    text_lower = text.lower()

    # 1. Extract amount
    result.amount = normalize_amount(text)
    if not result.amount:
        return result  # No amount found, bail out

    # 2. Infer category from keywords (simplified version)
    # In real code, this would call category_rules.classify_category()
    category_keywords = {
        "Alimentación": [
            "supermercado", "super", "jumbo", "comida", "almuerzo", "cena",
            "restaurante", "café", "pizza", "sushi", "pan", "panadería"
        ],
        "Transporte": [
            "uber", "taxi", "metro", "bus", "bencina", "peaje", "didi"
        ],
        "Salud": [
            "farmacia", "doctor", "médico", "clínica", "hospital", "remedio"
        ],
        "Hogar": [
            "luz", "agua", "gas", "arriendo", "internet", "condominio"
        ],
        "Entretenimiento": [
            "netflix", "spotify", "cine", "película", "teatro", "steam"
        ],
        "Ropa": [
            "ropa", "zapatos", "zapatillas", "camisa", "vestido", "h&m", "zara"
        ],
    }

    for category, keywords in category_keywords.items():
        if any(kw in text_lower for kw in keywords):
            result.category_hint = category
            break

    # 3. Infer merchant (simplified)
    known_merchants = [
        "jumbo", "lider", "unimarc", "tottus", "uber", "didi", "metro",
        "farmacia", "netflix", "spotify"
    ]
    for merchant in known_merchants:
        if merchant in text_lower:
            result.merchant_hint = merchant.title()
            break

    # 4. Extract note (remaining text after removing amount and keywords)
    note_text = text.split()
    result.note = " ".join(note_text[:20])  # First 20 words as note

    # 5. Calculate confidence
    confidence = 0.5  # Base

    if result.amount:
        confidence += 0.3  # Has amount

    if result.category_hint:
        confidence += 0.1  # Has category

    if result.merchant_hint:
        confidence += 0.1  # Has merchant

    result.confidence = min(confidence, 1.0)
    result.parse_method = "rules"

    return result
