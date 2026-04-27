"""Tests for text-based expense parser."""

from decimal import Decimal

import pytest

from app.parsers.text_parser import parse_expense_text


class TestParseExpenseText:
    """Test suite for parse_expense_text function."""

    def test_simple_expense(self) -> None:
        """Test basic expense parsing."""
        result = parse_expense_text("gasté 15 lucas en ropa")
        assert result.amount == Decimal("15000")
        assert result.currency == "CLP"
        assert result.category_hint == "Ropa"
        assert result.confidence > 0.7

    def test_with_merchant(self) -> None:
        """Test parsing with merchant name."""
        result = parse_expense_text("pagué jumbo 35 mil")
        assert result.amount == Decimal("35000")
        assert result.merchant_hint == "Jumbo"
        assert result.category_hint == "Alimentación"

    def test_restaurant_expense(self) -> None:
        """Test restaurant expense."""
        result = parse_expense_text("compré sushi por 18 mil")
        assert result.amount == Decimal("18000")
        assert result.category_hint == "Alimentación"

    def test_transport_expense(self) -> None:
        """Test transport expense."""
        result = parse_expense_text("uber 6500")
        assert result.amount == Decimal("6500")
        assert result.category_hint == "Transporte"
        assert result.merchant_hint == "Uber"

    def test_health_expense(self) -> None:
        """Test pharmacy/health expense."""
        result = parse_expense_text("farmacia 12.500")
        assert result.amount == Decimal("12500")
        assert result.category_hint == "Salud"

    def test_entertainment_expense(self) -> None:
        """Test entertainment expense."""
        result = parse_expense_text("netflix 10000")
        assert result.amount == Decimal("10000")
        assert result.category_hint == "Entretenimiento"

    def test_no_amount(self) -> None:
        """Test text without amount."""
        result = parse_expense_text("gasté en ropa")
        assert result.amount is None
        assert result.confidence == 0.0

    def test_amount_only(self) -> None:
        """Test amount without category."""
        result = parse_expense_text("5000")
        assert result.amount == Decimal("5000")
        # Without category, confidence should be lower
        assert result.confidence < 0.7

    def test_empty_text(self) -> None:
        """Test empty input."""
        result = parse_expense_text("")
        assert result.amount is None
        assert result.confidence == 0.0

    def test_note_extraction(self) -> None:
        """Test note extraction."""
        result = parse_expense_text("gasté 15 lucas en ropa nueva en la tienda del mall")
        assert result.amount == Decimal("15000")
        assert result.note is not None
        assert len(result.note) > 0

    def test_k_suffix(self) -> None:
        """Test parsing with 'k' suffix."""
        result = parse_expense_text("pagué 20k en zapatos")
        assert result.amount == Decimal("20000")
        assert result.category_hint == "Ropa"

    def test_mil_word(self) -> None:
        """Test parsing with 'mil' word."""
        result = parse_expense_text("comida 25 mil")
        assert result.amount == Decimal("25000")
        assert result.category_hint == "Alimentación"

    def test_currency_default(self) -> None:
        """Test default currency is CLP."""
        result = parse_expense_text("gasté 100")
        assert result.currency == "CLP"

    def test_parse_method_is_rules(self) -> None:
        """Test that parse_method is 'rules'."""
        result = parse_expense_text("gasté 50 lucas")
        assert result.parse_method == "rules"

    def test_confidence_scaling(self) -> None:
        """Test confidence increases with more information."""
        result1 = parse_expense_text("5000")  # amount only
        result2 = parse_expense_text("jumbo 5000")  # amount + merchant
        result3 = parse_expense_text("pagué jumbo 5000")  # amount + verb + merchant

        # More info should generally mean higher confidence
        assert result1.confidence <= result2.confidence
        assert result2.confidence <= result3.confidence

    def test_income_verb_sets_type_income(self) -> None:
        """Test income verb sets type to income."""
        result = parse_expense_text("recibí 4 millones de sueldo")
        assert result.type == "income"
        assert result.amount == Decimal("4000000")
        assert result.category_hint == "Sueldo"

    def test_income_phrase_sets_type_income(self) -> None:
        """Test income phrase sets type to income."""
        result = parse_expense_text("me pagaron el freelance 200 lucas")
        assert result.type == "income"
        assert result.amount == Decimal("200000")

    def test_expense_verb_sets_type_expense(self) -> None:
        """Test expense verb sets type to expense."""
        result = parse_expense_text("pagué uber 6.500")
        assert result.type == "expense"
        assert result.amount == Decimal("6500")
        assert result.category_hint == "Transporte"

    def test_income_category_restricted_to_income_applicable(self) -> None:
        """Test income categories are only applied to income."""
        result = parse_expense_text("recibí sueldo 1.800.000")
        assert result.type == "income"
        assert result.category_hint == "Sueldo"

    def test_expense_does_not_classify_as_income_category(self) -> None:
        """Test expense does not get classified as income category."""
        result = parse_expense_text("gasté 5.000 en comida")
        assert result.type == "expense"
        assert result.category_hint != "Sueldo"
        assert result.category_hint != "Otros Ingresos"

    def test_income_phrase_me_depositaron(self) -> None:
        """Test 'me depositaron' phrase triggers income type."""
        result = parse_expense_text("me depositaron 300 lucas")
        assert result.type == "income"
        assert result.amount == Decimal("300000")

    def test_income_phrase_cayo_el_sueldo(self) -> None:
        """Test 'cayó el sueldo' phrase triggers income type."""
        result = parse_expense_text("cayó el sueldo 2.500.000")
        assert result.type == "income"
        assert result.amount == Decimal("2500000")

    def test_income_phrase_me_llegó(self) -> None:
        """Test 'me llegó' phrase triggers income type."""
        result = parse_expense_text("me llegó pago 150 lucas")
        assert result.type == "income"
        assert result.amount == Decimal("150000")
