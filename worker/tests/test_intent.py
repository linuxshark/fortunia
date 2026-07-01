"""Tests del clasificador de intención ingreso vs gasto (worker/intent.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent import classify


# --- Ingresos ---------------------------------------------------------------

def test_sueldo_cobre_is_income():
    # Caso real reportado: se registraba como gasto.
    assert classify("cobré mi sueldo 4.404.000") == "income"


def test_recibi_is_income():
    assert classify("recibí 200.000 de un bono") == "income"


def test_vendi_is_income():
    assert classify("vendí la bici en 150.000") == "income"


def test_sueldo_noun_without_verb_is_income():
    assert classify("sueldo 1.200.000") == "income"


def test_freelance_is_income():
    assert classify("freelance 800.000") == "income"


def test_me_pagaron_is_income():
    assert classify("me pagaron 500.000 de honorarios") == "income"


# --- Gastos -----------------------------------------------------------------

def test_gaste_is_expense():
    assert classify("gasté 40.000 en bencina") == "expense"


def test_pague_is_expense():
    assert classify("pagué 8500 en almuerzo") == "expense"


def test_compre_is_expense():
    assert classify("compré 25.000 en ropa") == "expense"


def test_no_signal_defaults_to_expense():
    assert classify("40.000 supermercado") == "expense"


# --- Ambigüedad: gana la primera señal --------------------------------------

def test_pague_arriendo_is_expense():
    # 'pagué' (gasto) aparece antes que 'arriendo' (ingreso) -> gasto.
    assert classify("pagué el arriendo 300.000") == "expense"


def test_me_pagaron_arriendo_is_income():
    assert classify("me pagaron el arriendo 300.000") == "income"


def test_empty_defaults_to_expense():
    assert classify("") == "expense"
