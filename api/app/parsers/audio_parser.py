"""Audio transcript parser."""

from .text_parser import ParsedExpense, parse_expense_text


def parse_audio_transcript(transcript: str) -> ParsedExpense:
    """
    Parse audio transcript to extract expense data.

    Reuses text_parser with the transcript text.

    Args:
        transcript: Whisper transcript output

    Returns:
        ParsedExpense with extracted data
    """
    if not transcript:
        return ParsedExpense()

    # Reuse text parser
    result = parse_expense_text(transcript)

    # Mark as audio source
    result.parse_method = "audio"

    # If confidence is low, flag for confirmation
    if result.confidence < 0.6:
        result.confidence = max(result.confidence, 0.4)

    return result
