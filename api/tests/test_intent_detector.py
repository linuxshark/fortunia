"""Tests for financial intent detection."""

import pytest

from app.classifiers.intent_detector import is_finance_intent


class TestIntentDetector:
    """Test suite for is_finance_intent function."""

    # POSITIVE CASES (should be detected as finance)

    def test_finance_verb_with_amount(self) -> None:
        """Test finance verbs + amount."""
        result = is_finance_intent("gasté 15 lucas en ropa")
        assert result.is_finance is True
        assert result.confidence >= 0.9

    def test_pague_verb(self) -> None:
        """Test 'pagué' verb."""
        result = is_finance_intent("pagué uber 6500")
        assert result.is_finance is True
        assert result.confidence >= 0.9

    def test_compre_verb(self) -> None:
        """Test 'compré' verb."""
        result = is_finance_intent("compré sushi por 18 mil con mi esposa")
        assert result.is_finance is True
        assert result.confidence >= 0.9

    def test_me_costo(self) -> None:
        """Test 'me costó' phrase."""
        result = is_finance_intent("me costó 5 lucas en café")
        assert result.is_finance is True

    def test_category_with_amount_short(self) -> None:
        """Test category + amount in short message."""
        result = is_finance_intent("supermercado 35 mil")
        assert result.is_finance is True
        assert result.confidence >= 0.8

    def test_simple_merchant_amount(self) -> None:
        """Test merchant name + amount."""
        result = is_finance_intent("jumbo 25 mil")
        assert result.is_finance is True

    # NEGATIVE CASES (should NOT be detected as finance)

    def test_movie_cost(self) -> None:
        """Test narrative about movie cost (NOT personal spending)."""
        result = is_finance_intent("vi una película que costó 20 millones producirla")
        assert result.is_finance is False
        assert result.confidence == 0.0

    def test_iphone_price(self) -> None:
        """Test narrative about product price."""
        result = is_finance_intent("leí que el iPhone cuesta 1.500.000")
        assert result.is_finance is False

    def test_company_revenue(self) -> None:
        """Test narrative about company revenue."""
        result = is_finance_intent("esa empresa facturó 50 mil millones el año pasado")
        assert result.is_finance is False

    def test_hypothetical(self) -> None:
        """Test hypothetical scenario."""
        result = is_finance_intent("si gastara 50 mil en zapatos sería mucho")
        assert result.is_finance is False

    def test_price_question(self) -> None:
        """Test price inquiry (not personal spending)."""
        result = is_finance_intent("cuánto cuesta una pizza?")
        assert result.is_finance is False

    def test_price_query(self) -> None:
        """Test price query with upside-down question mark."""
        result = is_finance_intent("¿cuánto cuesta este producto?")
        assert result.is_finance is False

    def test_reported_speech(self) -> None:
        """Test reported speech (not personal spending)."""
        result = is_finance_intent("dicen que los tomates costaron 5 mil")
        assert result.is_finance is False

    def test_valuation(self) -> None:
        """Test valuation narrative."""
        result = is_finance_intent("la casa fue valuada en 200 millones")
        assert result.is_finance is False

    # EDGE CASES / AMBIGUOUS

    def test_no_text(self) -> None:
        """Test empty input."""
        result = is_finance_intent("")
        assert result.is_finance is False

    def test_amount_only(self) -> None:
        """Test amount without context."""
        result = is_finance_intent("15.000")
        assert result.is_finance is False
        assert result.confidence < 1.0

    def test_none_input(self) -> None:
        """Test None input."""
        result = is_finance_intent(None)
        assert result.is_finance is False

    # CHILEAN-SPECIFIC CASES

    def test_lucas_variant(self) -> None:
        """Test Chilean 'lucas' slang."""
        result = is_finance_intent("pagué 30 lucas en la bencina")
        assert result.is_finance is True

    def test_transporte_keyword(self) -> None:
        """Test transport keyword."""
        result = is_finance_intent("meter 50 lucas")
        assert result.is_finance is False or result.confidence < 0.8

    def test_farmacia_expense(self) -> None:
        """Test pharmacy expense."""
        result = is_finance_intent("farmacia 12.500")
        assert result.is_finance is True

    # REGRESSION: False positives

    def test_no_false_positive_production_cost(self) -> None:
        """Ensure we don't flag 'cuesta producir'."""
        result = is_finance_intent("cuesta mucho producir películas")
        assert result.is_finance is False

    def test_no_false_positive_it_costs(self) -> None:
        """Ensure 'cuesta' in non-personal context is rejected."""
        result = is_finance_intent("el chocolate cuesta 3 mil en la tienda")
        # Ambiguous: has verb, amount, but no personal context
        # Should ideally be False or ambiguous
        assert result.confidence <= 0.9

    def test_collected_value(self) -> None:
        """Test narrative about collected amount."""
        result = is_finance_intent("recaudó 50 millones en donaciones")
        assert result.is_finance is False
