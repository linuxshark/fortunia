"""Standalone finance intent detector for Kraken (zero dependencies)."""

import re
from dataclasses import dataclass


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
    "cobré", "invertir", "donar"
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
    Detect if text represents a personal finance transaction (standalone version).

    This is a mirror of the API's intent_detector, optimized for local use in Kraken.
    Zero dependencies: only stdlib `re`.

    Rules:
    - Finance verbs + amount → is_finance=True, confidence=0.95
    - Category keyword + amount → is_finance=True, confidence=0.85
    - Negative context → is_finance=False
    - Ambiguous (amount only) → needs_llm=True
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
                reason=f"negative_context"
            )

    # 2. Check for finance verbs
    has_finance_verb = any(verb in text_words for verb in FINANCE_VERBS)
    if has_finance_verb:
        # Check if there's an amount (contains digits)
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
        "transporte", "café", "zapatos", "luz", "agua", "jumbo",
        "lider", "metro", "netflix", "spotify"
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


if __name__ == "__main__":
    # CLI usage for testing
    import sys

    if len(sys.argv) < 2:
        print("Usage: finance_detector.py '<message>'")
        sys.exit(1)

    msg = sys.argv[1]
    result = is_finance_intent(msg)

    # Output format for Kraken to parse
    if result.is_finance:
        print(f"IS_FINANCE=true")
        print(f"CONFIDENCE={result.confidence}")
        print(f"REASON={result.reason}")
    elif result.needs_llm:
        print(f"IS_FINANCE=ambiguous")
        print(f"CONFIDENCE={result.confidence}")
        print(f"NEEDS_LLM=true")
    else:
        print(f"IS_FINANCE=false")
        print(f"CONFIDENCE={result.confidence}")
        print(f"REASON={result.reason}")
