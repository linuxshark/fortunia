"""Income-specific tests for intent detector (minimal setup, no DB)."""

from app.classifiers.intent_detector import is_finance_intent


def test_income_recibi_sueldo() -> None:
    """Test 'recibí' verb with salary."""
    result = is_finance_intent("recibí 4000000 de sueldo")
    assert result.is_finance is True, f"Expected finance=True, got {result}"
    assert result.confidence >= 0.85


def test_income_recibi_unaccented() -> None:
    """Test 'recibi' (unaccented) verb."""
    result = is_finance_intent("recibi mi sueldo este mes 1500000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_cobre_project() -> None:
    """Test 'cobré' verb with project income."""
    result = is_finance_intent("cobré el proyecto 350000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_pagaron() -> None:
    """Test 'me pagaron' phrase."""
    result = is_finance_intent("me pagaron el freelance 200000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_depositaron() -> None:
    """Test 'me depositaron' phrase."""
    result = is_finance_intent("me depositaron 1200000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_transfirieron() -> None:
    """Test 'me transfirieron' phrase."""
    result = is_finance_intent("me transfirieron 500000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_cayo_sueldo() -> None:
    """Test 'cayó el sueldo' phrase."""
    result = is_finance_intent("cayó el sueldo 1800000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_cayo_sueldo_unaccented() -> None:
    """Test 'cayo el sueldo' phrase (unaccented)."""
    result = is_finance_intent("cayo el sueldo hoy 1800000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_llego_pago() -> None:
    """Test 'me llegó' phrase."""
    result = is_finance_intent("me llegó el pago 450000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_llego_transferencia() -> None:
    """Test 'me llego' phrase (unaccented)."""
    result = is_finance_intent("me llego transferencia 300000")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_gane_project() -> None:
    """Test 'gané' verb."""
    result = is_finance_intent("gané 250000 en el proyecto")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_gane_unaccented() -> None:
    """Test 'gane' verb (unaccented)."""
    result = is_finance_intent("gane 250000 en el proyecto")
    assert result.is_finance is True
    assert result.confidence >= 0.85


def test_income_me_entraron() -> None:
    """Test 'me entraron' phrase."""
    result = is_finance_intent("me entraron 600000 hoy")
    assert result.is_finance is True
    assert result.confidence >= 0.85
