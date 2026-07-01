"""Parser de ingresos por texto libre ("cobré 5.000.000 de sueldo")."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from text_income import parse_income          # noqa: E402
from text_expense import ParseError           # noqa: E402


# --- monto ---

def test_sueldo_basico():
    r = parse_income("cobré 5.000.000 de sueldo")
    assert r["amount"] == 5_000_000
    assert r["source_text"] == "sueldo"
    assert r["kind"] == "income"


def test_venta_guitarra():
    r = parse_income("vendí una guitarra por 350.000")
    assert r["amount"] == 350_000
    assert "guitarra" in r["source_text"]


def test_bono_multiplicador_mil():
    r = parse_income("recibí 200 mil de bono")
    assert r["amount"] == 200_000
    assert r["source_text"] == "bono"


def test_palo_slang():
    r = parse_income("me pagaron 1 palo")
    assert r["amount"] == 1_000_000


def test_millones_multiplicador():
    r = parse_income("gané 2 millones freelance")
    assert r["amount"] == 2_000_000
    assert r["source_text"] == "freelance"


def test_monto_sin_separador():
    assert parse_income("recibí 40000 de sueldo")["amount"] == 40_000


def test_monto_con_signo_peso():
    r = parse_income("$1.500.000 de sueldo")
    assert r["amount"] == 1_500_000
    assert r["source_text"] == "sueldo"


def test_luca_slang():
    assert parse_income("me dieron 500 lucas de bono")["amount"] == 500_000


def test_kind_siempre_income():
    assert parse_income("cobré 1000 de sueldo")["kind"] == "income"


def test_raw_preserva_original():
    txt = "cobré 5.000.000 de sueldo"
    assert parse_income(txt)["raw"] == txt


# --- errores ---

def test_sin_monto_lanza_error():
    with pytest.raises(ParseError):
        parse_income("hola como estas")


def test_texto_vacio_lanza_error():
    with pytest.raises(ParseError):
        parse_income("   ")


def test_monto_cero_invalido():
    with pytest.raises(ParseError):
        parse_income("cobré 0 de sueldo")


def test_monto_excesivo_invalido():
    with pytest.raises(ParseError):
        parse_income("cobré 9999999999999 de sueldo")


def test_texto_demasiado_largo():
    with pytest.raises(ParseError):
        parse_income("cobré 1000 de " + "x" * 600)
