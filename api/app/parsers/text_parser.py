"""Text-based expense parser."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .normalizer import normalize_amount
from app.classifiers.category_rules import classify_category


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
        return result

    # 2. Infer category using the shared classifier
    category_name, _cat_confidence = classify_category(text)
    if category_name:
        result.category_hint = category_name

    # 3. Infer merchant from known names
    known_merchants = [
        "jumbo", "lider", "líder", "unimarc", "tottus", "santa isabel",
        "uber", "didi", "cabify", "metro",
        "farmacia", "salcobrand", "cruz verde",
        "netflix", "spotify", "steam",
    ]
    for merchant in known_merchants:
        if merchant in text_lower:
            result.merchant_hint = merchant.title()
            break

    # 4. Keep the original text as note (first 20 words)
    result.note = " ".join(text.split()[:20])

    # 5. Calculate confidence
    confidence = 0.5
    if result.amount:
        confidence += 0.3
    if result.category_hint:
        confidence += 0.1
    if result.merchant_hint:
        confidence += 0.1

    result.confidence = min(confidence, 1.0)
    result.parse_method = "rules"

    return result
