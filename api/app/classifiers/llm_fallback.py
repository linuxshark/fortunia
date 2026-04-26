"""LLM fallback for ambiguous cases (optional, v2)."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .intent_detector import IntentResult


async def llm_classify(text: str) -> "IntentResult":
    """
    LLM-based intent classification (optional, v2).

    Currently disabled. In v2, integrate with:
    - Anthropic API
    - OpenAI API
    - Local Qwen 3B
    """
    from .intent_detector import IntentResult

    return IntentResult(
        is_finance=False,
        confidence=0.0,
        needs_llm=False,
        reason="llm_disabled"
    )
