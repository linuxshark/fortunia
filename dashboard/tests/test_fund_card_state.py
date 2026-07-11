import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from queries import fund_card_state  # noqa: E402


def test_pendiente_sin_pagos():
    assert fund_card_state(0, 600000) == ("pendiente", 0)


def test_parcial_consumo_intermedio():
    # 194.330 de 600.000 -> parcial, 32%
    assert fund_card_state(194330, 600000) == ("parcial", 32)


def test_pagado_exacto():
    assert fund_card_state(500000, 500000) == ("pagado", 100)


def test_excedido_sobre_presupuesto():
    assert fund_card_state(700000, 600000) == ("excedido", 100)


def test_presupuesto_cero_con_pago_es_excedido():
    assert fund_card_state(1000, 0) == ("excedido", 100)


def test_pct_redondea():
    # 1 de 3 -> 33%
    assert fund_card_state(1, 3) == ("parcial", 33)
