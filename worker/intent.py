"""Clasificador determinista de intención ingreso vs gasto — sin LLM, token-free.

openclaw postea TODO mensaje de texto al worker; este módulo decide si el texto
describe un ingreso ("cobré mi sueldo 4.404.000") o un gasto ("gasté 40.000 en
bencina") para enrutarlo al flujo correcto. Es puro (sin DB), testeable.

Regla: gana la señal (verbo/sustantivo) que aparezca PRIMERO en el texto. Así
"pagué el arriendo" → gasto (verbo de gasto antes del sustantivo de ingreso),
y "cobré mi sueldo" → ingreso. Sin señales claras, el default es 'expense'
(comportamiento histórico: openclaw mandaba todo a /text).
"""
from __future__ import annotations

import re

# Señales de ingreso: verbos (text_income._INCOME_VERBS) + sustantivos de los
# aliases de ingreso (db/05_incomes.sql). Frases multi-palabra incluidas.
_INCOME_SIGNALS = (
    "cobré", "cobre", "recibí", "recibi", "gané", "gane",
    "vendí", "vendi", "venta", "ingresé", "ingrese", "me pagaron",
    "sueldo", "salario", "bono", "comisión", "comision",
    "arriendo", "arrienda", "freelance", "consultoría", "consultoria",
    "honorarios", "dividendo", "finiquito", "aguinaldo",
)

# Señales de gasto: verbos de text_expense._EXPENSE_VERBS.
_EXPENSE_SIGNALS = (
    "gaste", "gasté", "gasto", "pague", "pagué", "compre", "compré", "compra",
    "invertí", "inverti", "saque", "saqué", "deposite", "deposité",
)


def _first_match_pos(text: str, signals: tuple[str, ...]) -> int | None:
    """Posición de la señal que aparece primero (límite de palabra). None si ninguna."""
    best: int | None = None
    for s in signals:
        m = re.search(r"\b" + re.escape(s) + r"\b", text)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


def classify(text: str) -> str:
    """Devuelve 'income' o 'expense'. Default 'expense' si no hay señales."""
    t = (text or "").lower()
    inc = _first_match_pos(t, _INCOME_SIGNALS)
    exp = _first_match_pos(t, _EXPENSE_SIGNALS)

    if inc is None and exp is None:
        return "expense"
    if inc is None:
        return "expense"
    if exp is None:
        return "income"
    return "income" if inc <= exp else "expense"
