"""Parser de gastos por texto libre ("gaste 40.000 en bencina")."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from text_expense import ParseError, parse_expense  # noqa: E402


# ---------------- monto (CLP) ----------------

def test_caso_ejemplo():
    r = parse_expense("gaste 40.000 en bencina")
    assert r["amount"] == 40000
    assert r["category_text"] == "bencina"
    assert r["kind"] == "expense"


def test_monto_sin_separador():
    assert parse_expense("gaste 40000 en bencina")["amount"] == 40000


def test_monto_con_signo_peso():
    r = parse_expense("$40.000 bencina")
    assert r["amount"] == 40000
    assert r["category_text"] == "bencina"


def test_punto_como_miles_no_decimal():
    # CLP no tiene decimales: 1.234 son mil doscientos treinta y cuatro
    assert parse_expense("pagué 1.234 en pan")["amount"] == 1234


def test_multiplicador_mil():
    assert parse_expense("gaste 40 mil en bencina")["amount"] == 40000


def test_multiplicador_k():
    assert parse_expense("gaste 40k en bencina")["amount"] == 40000


def test_multiplicador_luca_slang():
    assert parse_expense("5 lucas en cerveza")["amount"] == 5000


# ---------------- categoria ----------------

def test_categoria_tras_preposicion_de():
    assert parse_expense("gaste 5000 de almuerzo")["category_text"] == "almuerzo"


def test_categoria_tras_preposicion_para():
    assert parse_expense("pague 3000 para el metro")["category_text"] == "el metro"


def test_categoria_sin_preposicion():
    # monto al inicio, resto es la categoria
    assert parse_expense("12500 supermercado")["category_text"] == "supermercado"


def test_categoria_otros_cuando_falta():
    assert parse_expense("gaste 40.000")["category_text"] == "otros"


# ---------------- intent / clasificacion ----------------

def test_palabras_gasto_variadas():
    for verbo in ("gaste", "gasté", "pague", "pagué", "compré", "gasto de"):
        assert parse_expense(f"{verbo} 1000 en pan")["kind"] == "expense"


# ---------------- validacion / errores ----------------

def test_sin_monto_lanza_error():
    with pytest.raises(ParseError):
        parse_expense("hola como estas")


def test_texto_vacio_lanza_error():
    with pytest.raises(ParseError):
        parse_expense("   ")


def test_monto_cero_invalido():
    with pytest.raises(ParseError):
        parse_expense("gaste 0 en nada")


def test_monto_excesivo_invalido():
    with pytest.raises(ParseError):
        parse_expense("gaste 9999999999999 en algo")


def test_texto_demasiado_largo():
    with pytest.raises(ParseError):
        parse_expense("gaste 1000 en " + "x" * 600)
