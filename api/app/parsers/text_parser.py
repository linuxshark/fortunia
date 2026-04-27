"""Text-based expense parser."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .normalizer import normalize_amount
from app.classifiers.category_rules import classify_category


# Income detection verbs and keywords
INCOME_VERBS = {
    "recibí", "recibi", "recibe", "recibir",
    "cobré", "cobre", "cobrar",
    "gané", "gane", "ganar",
}

INCOME_PHRASES = {
    "me pagaron", "me depositaron", "me transfirieron",
    "cayó el sueldo", "cayo el sueldo",
    "me llegó", "me llego", "me entraron",
}

INCOME_KEYWORDS = {
    "sueldo", "salario", "remuneración", "remuneracion",
    "freelance", "honorario", "transferencia recibida",
    "ingreso", "pago recibido",
}


def _detect_transaction_type(text: str) -> str:
    """
    Detect if transaction is 'income' or 'expense' from text.

    Returns: "income" or "expense"
    """
    if not text:
        return "expense"

    text_lower = text.lower()
    text_words = set(text_lower.split())

    # Check for income verbs
    if any(verb in text_words for verb in INCOME_VERBS):
        return "income"

    # Check for income phrases
    if any(phrase in text_lower for phrase in INCOME_PHRASES):
        return "income"

    # Check for income keywords
    if any(keyword in text_lower for keyword in INCOME_KEYWORDS):
        return "income"

    # Default to expense
    return "expense"


@dataclass
class ParsedExpense:
    """Result of parsing an expense text."""

    amount: Optional[Decimal] = None
    currency: str = "CLP"
    type: str = "expense"  # "expense" or "income"
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
            type='expense',
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

    # 2. Detect transaction type (income or expense)
    result.type = _detect_transaction_type(text)

    # 3. Infer category using the shared classifier, filtered by transaction type
    category_name, _cat_confidence = classify_category(text, result.type)
    if category_name:
        result.category_hint = category_name

    # 4. Infer merchant from known names
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

    # 5. Keep the original text as note (first 20 words)
    result.note = " ".join(text.split()[:20])

    # 6. Calculate confidence
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
