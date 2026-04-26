"""Financial intent detection — zero LLM."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class IntentResult:
    """Result of intent detection."""

    is_finance: bool
    confidence: float
    needs_llm: bool = False
    reason: str = ""


# Finance verbs in Spanish (Chilean context)
FINANCE_VERBS = {
    "gasté", "gaste", "pagué", "pague", "compré", "compre",
    "me costó", "costó", "costo", "salió", "transferí", "invertí",
    "gasté", "pagué", "invertir", "donar", "cobré", "cobré"
}

# Negative context (narrative, not personal spending)
NEGATIVE_CONTEXT = {
    "vi una película",
    "leí que",
    "dicen que",
    "según",
    "valuada en",
    "recaudó",
    "facturó",
    "cuesta producir",
    "si gastara",
    "cuánto cuesta",
    "¿cuánto cuesta",
}


def is_finance_intent(text: str) -> IntentResult:
    """
    Detect if text represents a personal finance transaction.

    Uses rules only (zero LLM):
    - Finance verbs + amount → is_finance=True, confidence=0.95
    - Category keyword + amount → is_finance=True, confidence=0.85
    - Negative context → is_finance=False
    - Ambiguous (amount only) → needs_llm=True

    Examples:
        "gasté 15 lucas en ropa" → is_finance=True, confidence=0.95
        "pagué uber 6500" → is_finance=True, confidence=0.95
        "compré sushi por 18 mil" → is_finance=True, confidence=0.95
        "vi una película que costó 20 millones" → is_finance=False, confidence=0.0
        "leí que el iPhone cuesta 1.5 millones" → is_finance=False, confidence=0.0
        "si gastara 50 mil en zapatos" → is_finance=False, confidence=0.0
    """
    if not text or not isinstance(text, str):
        return IntentResult(is_finance=False, confidence=0.0, reason="empty_text")

    text_lower = text.lower()
    text_words = set(text_lower.split())

    # 1. Check for negative context (NOT a finance transaction)
    for neg_phrase in NEGATIVE_CONTEXT:
        if neg_phrase in text_lower:
            return IntentResult(
                is_finance=False,
                confidence=0.0,
                reason=f"negative_context:{neg_phrase}"
            )

    # 2. Check for finance verbs
    has_finance_verb = any(verb in text_words for verb in FINANCE_VERBS)
    if has_finance_verb:
        # Check if there's an amount (simple heuristic: contains numbers)
        if any(c.isdigit() for c in text):
            return IntentResult(
                is_finance=True,
                confidence=0.95,
                reason="finance_verb_with_amount"
            )

    # 3. Check for amount without verb (ambiguous)
    has_amount = any(c.isdigit() for c in text)
    has_category = any(keyword in text_lower for keyword in [
        "supermercado", "uber", "farmacia", "ropa", "comida",
        "transporte", "café", "zapatos", "luz", "agua"
    ])

    if has_amount and not has_finance_verb:
        if has_category and len(text.split()) < 12:
            # Short message with category + amount likely a transaction
            return IntentResult(
                is_finance=True,
                confidence=0.85,
                reason="amount_category_short"
            )
        else:
            # Ambiguous — could be a price inquiry or narrative
            return IntentResult(
                is_finance=False,
                confidence=0.5,
                needs_llm=True,
                reason="amount_only_ambiguous"
            )

    # Default: not a transaction
    return IntentResult(
        is_finance=False,
        confidence=0.0,
        reason="no_finance_signals"
    )
