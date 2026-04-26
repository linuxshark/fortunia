"""Tests for amount normalization."""

from decimal import Decimal

import pytest

from app.parsers.normalizer import normalize_amount


class TestNormalizeAmount:
    """Test suite for normalize_amount function."""

    def test_lucas_format(self) -> None:
        """Test 'lucas' (Chilean slang for 1000s)."""
        assert normalize_amount("15 lucas") == Decimal("15000")
        assert normalize_amount("gasté 15 lucas en ropa") == Decimal("15000")
        assert normalize_amount("pagué 20 lucas") == Decimal("20000")

    def test_k_suffix(self) -> None:
        """Test 'k' suffix (thousand)."""
        assert normalize_amount("15k") == Decimal("15000")
        assert normalize_amount("15 k") == Decimal("15000")
        assert normalize_amount("10K") == Decimal("10000")
        assert normalize_amount("5.5k") == Decimal("5500")

    def test_mil_word(self) -> None:
        """Test 'mil' (thousand in Spanish)."""
        assert normalize_amount("15 mil") == Decimal("15000")
        assert normalize_amount("10mil") == Decimal("10000")
        assert normalize_amount("20 miles") == Decimal("20000")

    def test_millones_word(self) -> None:
        """Test 'millones' (millions)."""
        assert normalize_amount("1.5 millones") == Decimal("1500000")
        assert normalize_amount("2 millones") == Decimal("2000000")

    def test_m_suffix(self) -> None:
        """Test 'M' suffix (million)."""
        assert normalize_amount("1M") == Decimal("1000000")
        assert normalize_amount("1.5 m") == Decimal("1500000")

    def test_chile_format_thousands(self) -> None:
        """Test Chilean format with . as thousand separator."""
        assert normalize_amount("15.000") == Decimal("15000")
        assert normalize_amount("1.500.000") == Decimal("1500000")
        assert normalize_amount("10.500") == Decimal("10500")

    def test_currency_prefix(self) -> None:
        """Test currency symbols."""
        assert normalize_amount("$15.000") == Decimal("15000")
        assert normalize_amount("$15000") == Decimal("15000")
        assert normalize_amount("€100") == Decimal("100")

    def test_decimal_comma(self) -> None:
        """Test decimal separator (comma)."""
        assert normalize_amount("15,50") == Decimal("15.50")
        assert normalize_amount("100,99") == Decimal("100.99")

    def test_decimal_period(self) -> None:
        """Test decimal separator (period)."""
        assert normalize_amount("15.50") == Decimal("15.50")
        assert normalize_amount("100.01") == Decimal("100.01")

    def test_simple_integers(self) -> None:
        """Test simple integer amounts."""
        assert normalize_amount("100") == Decimal("100")
        assert normalize_amount("5000") == Decimal("5000")
        assert normalize_amount("999") == Decimal("999")

    def test_no_amount(self) -> None:
        """Test cases with no amount."""
        assert normalize_amount("") is None
        assert normalize_amount("sin monto") is None
        assert normalize_amount("texto sin números") is None

    def test_invalid_input(self) -> None:
        """Test invalid inputs."""
        assert normalize_amount(None) is None
        assert normalize_amount("   ") is None

    def test_complex_sentences(self) -> None:
        """Test extraction from complex sentences."""
        assert normalize_amount("gasté 15 lucas en ropa") == Decimal("15000")
        assert normalize_amount("pagué uber 6500") == Decimal("6500")
        assert normalize_amount("compré sushi por 18 mil") == Decimal("18000")
        assert normalize_amount("cuesta $25.500 el kilo") == Decimal("25500")

    def test_edge_cases(self) -> None:
        """Test edge cases."""
        assert normalize_amount("0.50") == Decimal("0.50")
        assert normalize_amount("0,5") == Decimal("0.5")
        # Very large numbers
        assert normalize_amount("999.999.999") == Decimal("999999999")
