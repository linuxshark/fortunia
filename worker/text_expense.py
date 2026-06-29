"""Parser determinista de gastos en texto libre — sin LLM, token-free.

Convierte "gaste 40.000 en bencina" en {amount: 40000, category_text: "bencina",
kind: "expense"}. CLP no tiene decimales y usa el punto como separador de miles,
así que los montos se reducen a enteros (reusa normalize.clp_to_int).

La resolución de categoría NO vive aquí: el texto de categoría se pasa luego a
categorize.categorize() para mapearlo a item_aliases. Esto mantiene el parser
puro (sin DB) y testeable sin dependencias.
"""
from __future__ import annotations

import re

from normalize import clp_to_int

MAX_LEN = 500
MAX_AMOUNT = 1_000_000_000  # mil millones CLP — techo anti-basura

# Verbos de gasto (también sirven para limpiar la categoría cuando va antes del monto)
_EXPENSE_VERBS = (
    "gaste", "gasté", "gasto", "pague", "pagué", "compre", "compré", "compra",
    "invertí", "inverti", "saque", "saqué", "deposite", "deposité",
)

# Multiplicadores: jerga chilena incluida (luca = 1.000, palo = 1.000.000)
_MULTIPLIERS = {
    "mil": 1_000,
    "k": 1_000,
    "luca": 1_000, "lucas": 1_000,
    "palo": 1_000_000, "palos": 1_000_000,
    "millon": 1_000_000, "millón": 1_000_000,
    "millones": 1_000_000,
}

# número (con puntos de miles opcionales) + multiplicador opcional, $ opcional
_AMOUNT = re.compile(
    r"\$?\s*(\d[\d.]*\d|\d)\s*"
    r"(mil|millones|millón|millon|lucas|luca|palos|palo|k)?",
    re.IGNORECASE,
)

# preposiciones que introducen la categoría ("en bencina", "de almuerzo")
_LEADING_PREP = re.compile(r"^(?:en|de|del|para|por)\b\s*", re.IGNORECASE)


class ParseError(ValueError):
    """El texto no representa un gasto procesable (sin monto, monto inválido…)."""


def _clean_category(text: str) -> str:
    text = text.strip(" .,;:-–—")
    text = _LEADING_PREP.sub("", text).strip()
    return text


def _strip_verbs(text: str) -> str:
    for v in _EXPENSE_VERBS:
        if text.lower().startswith(v):
            return text[len(v):].strip()
    return text


def parse_expense(text: str) -> dict:
    """Parsea texto libre a un gasto estructurado.

    Returns dict con: amount (int CLP), category_text (str), kind ('expense'),
    raw (texto original normalizado). Lanza ParseError si no hay monto válido.
    """
    if not text or not text.strip():
        raise ParseError("texto vacío")
    raw = text.strip()
    if len(raw) > MAX_LEN:
        raise ParseError(f"texto excede {MAX_LEN} caracteres")

    t = raw.lower()
    m = _AMOUNT.search(t)
    if not m:
        raise ParseError("no se encontró un monto en el texto")

    base = clp_to_int(m.group(1))
    if base is None:
        raise ParseError("monto ilegible")
    mult = _MULTIPLIERS.get(m.group(2).lower(), 1) if m.group(2) else 1
    amount = base * mult

    if amount <= 0:
        raise ParseError("el monto debe ser mayor a cero")
    if amount > MAX_AMOUNT:
        raise ParseError(f"monto fuera de rango (>{MAX_AMOUNT})")

    after = _clean_category(t[m.end():])
    category = after or _clean_category(_strip_verbs(t[: m.start()])) or "otros"

    return {"amount": amount, "category_text": category, "kind": "expense", "raw": raw}
