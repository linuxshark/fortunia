"""Tests for audio transcript parser."""

from decimal import Decimal

import pytest

from app.parsers.audio_parser import parse_audio_transcript


class TestAudioParser:
    """Test suite for parse_audio_transcript function."""

    def test_simple_audio_transcript(self) -> None:
        """Test basic audio transcript parsing."""
        transcript = "gasté quince mil en comida"
        result = parse_audio_transcript(transcript)
        assert result.amount == Decimal("15000")
        assert result.parse_method == "audio"

    def test_casual_speech_parsing(self) -> None:
        """Test parsing from casual/natural speech."""
        transcript = "pagué el uber cinco mil quinientos"
        result = parse_audio_transcript(transcript)
        # Should extract 5500 or 5000
        assert result.amount is not None

    def test_category_inference_from_audio(self) -> None:
        """Test category is inferred from transcript."""
        transcript = "compré sushi por dieciocho mil"
        result = parse_audio_transcript(transcript)
        assert result.category_hint == "Alimentación"

    def test_low_confidence_flag(self) -> None:
        """Test that low confidence is flagged."""
        # Ambiguous transcript (no clear amount or category)
        transcript = "fue caro"
        result = parse_audio_transcript(transcript)
        # Should have low confidence
        assert result.confidence < 0.8

    def test_empty_transcript(self) -> None:
        """Test empty transcript."""
        result = parse_audio_transcript("")
        assert result.amount is None

    def test_none_input(self) -> None:
        """Test None input."""
        result = parse_audio_transcript(None)
        assert result.amount is None

    def test_detailed_speech(self) -> None:
        """Test detailed speech with multiple details."""
        transcript = "pagué en jumbo treinta y cinco mil en alimentos"
        result = parse_audio_transcript(transcript)
        assert result.amount == Decimal("35000")
        assert result.category_hint == "Alimentación"
        assert result.confidence >= 0.7

    def test_parse_method_is_audio(self) -> None:
        """Test that parse_method is set to 'audio'."""
        transcript = "gasté 5 lucas"
        result = parse_audio_transcript(transcript)
        assert result.parse_method == "audio"

    def test_numeric_speech(self) -> None:
        """Test numeric speech patterns."""
        transcript = "cinco mil pesos en café"
        result = parse_audio_transcript(transcript)
        assert result.amount == Decimal("5000")
