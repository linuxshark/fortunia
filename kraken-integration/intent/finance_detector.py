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


# Finance verbs — single tokens (checked against word set)
FINANCE_VERBS_SINGLE = {
    "gasté", "gaste", "pagué", "pague", "compré", "compre",
    "costó", "costo", "salió", "salio", "transferí", "transferi",
    "invertí", "inverti", "invertir", "donar", "cobré", "cobre",
}

# Finance verb phrases — checked as substrings of the lowercased text
FINANCE_VERB_PHRASES = {
    "me costó", "me costo", "me salió", "me salio",
}

# Negative context — both accented and unaccented variants
NEGATIVE_CONTEXT = {
    "vi una película", "vi una pelicula",
    "leí que", "lei que",
    "dicen que",
    "según", "segun",
    "valuada en",
    "recaudó", "recaudo",
    "facturó", "facturo",
    "cuesta producir",
    "si gastara",
    "cuánto cuesta", "cuanto cuesta",
    "¿cuánto cuesta", "¿cuanto cuesta",
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
                reason="negative_context"
            )

    # 2. Check for finance verbs (single-word and multi-word)
    has_finance_verb = (
        any(verb in text_words for verb in FINANCE_VERBS_SINGLE)
        or any(phrase in text_lower for phrase in FINANCE_VERB_PHRASES)
    )
    if has_finance_verb:
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
        "transporte", "café", "cafe", "zapatos", "luz", "agua",
        "jumbo", "lider", "líder", "metro", "netflix", "spotify",
    ])

    if has_amount and not has_finance_verb:
        if has_category and len(text.split()) < 12:
            return IntentResult(
                is_finance=True,
                confidence=0.85,
                reason="amount_category_short"
            )
        else:
            return IntentResult(
                is_finance=False,
                confidence=0.5,
                needs_llm=True,
                reason="amount_only_ambiguous"
            )

    return IntentResult(
        is_finance=False,
        confidence=0.0,
        reason="no_finance_signals"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: finance_detector.py '<message>'")
        sys.exit(1)

    msg = sys.argv[1]
    result = is_finance_intent(msg)

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
