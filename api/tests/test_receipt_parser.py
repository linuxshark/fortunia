"""Tests for receipt OCR parser."""

from decimal import Decimal

import pytest

from app.parsers.receipt_parser import parse_receipt


class TestReceiptParser:
    """Test suite for parse_receipt function."""

    def test_basic_receipt(self) -> None:
        """Test basic receipt parsing."""
        ocr_text = """
        JUMBO
        RUT 76.123.456-1

        TOTAL A PAGAR: 25.500

        Gracias por su compra
        """
        result = parse_receipt(ocr_text)
        assert result.amount == Decimal("25500")
        assert result.category_hint == "Alimentación"

    def test_total_variations(self) -> None:
        """Test different TOTAL formats."""
        # Format 1: TOTAL A PAGAR
        ocr1 = "TOTAL A PAGAR: 15000"
        result1 = parse_receipt(ocr1)
        assert result1.amount is not None

        # Format 2: TOTAL:
        ocr2 = "TOTAL: 35.000"
        result2 = parse_receipt(ocr2)
        assert result2.amount is not None

    def test_merchant_extraction(self) -> None:
        """Test merchant name extraction."""
        ocr_text = """
        LIDER
        Avda Providencia 1234
        Santiago

        TOTAL: 12500
        """
        result = parse_receipt(ocr_text)
        assert result.merchant_hint == "LIDER"

    def test_no_amount(self) -> None:
        """Test receipt without detectable amount."""
        ocr_text = "Some text without amount"
        result = parse_receipt(ocr_text)
        assert result.amount is None

    def test_confidence_with_amount_only(self) -> None:
        """Test confidence increases with more data."""
        ocr1 = "TOTAL: 15000"
        result1 = parse_receipt(ocr1)

        ocr2 = """
        JUMBO
        TOTAL: 15000
        RUT 76.123.456-1
        """
        result2 = parse_receipt(ocr2)

        # More info should give higher confidence
        assert result2.confidence >= result1.confidence

    def test_category_inference_pharmacy(self) -> None:
        """Test category inference from merchant."""
        ocr_text = """
        FARMACIA CRUZ VERDE
        TOTAL: 8500
        """
        result = parse_receipt(ocr_text)
        assert result.category_hint == "Salud"

    def test_empty_input(self) -> None:
        """Test empty OCR text."""
        result = parse_receipt("")
        assert result.amount is None
        assert result.confidence == 0.5  # Base confidence

    def test_parse_method_is_ocr(self) -> None:
        """Test that parse_method is set to 'ocr'."""
        ocr_text = "TOTAL: 5000"
        result = parse_receipt(ocr_text)
        assert result.parse_method == "ocr"
