"""Parser determinista de ingresos en texto libre — sin LLM, token-free.

Convierte "cobré 5.000.000 de sueldo" en {amount: 5000000, source_text: "sueldo",
kind: "income"}. CLP no tiene decimales; reutiliza normalize.clp_to_int y la
clase ParseError de text_expense (mismo dominio de error).
"""
from __future__ import annotations

import re

from normalize import clp_to_int
from text_expense import ParseError  # reuse — same exception domain

MAX_LEN = 500
MAX_AMOUNT = 1_000_000_000

_INCOME_VERBS = (
    "cobré", "cobre", "recibí", "recibi", "gané", "gane",
    "vendí", "vendi", "ingresé", "ingrese", "me pagaron",
)

_MULTIPLIERS = {
    "mil": 1_000,
    "k": 1_000,
    "luca": 1_000, "lucas": 1_000,
    "palo": 1_000_000, "palos": 1_000_000,
    "millon": 1_000_000, "millón": 1_000_000,
    "millones": 1_000_000,
}

_AMOUNT = re.compile(
    r"\$?\s*(\d[\d.]*\d|\d)\s*"
    r"(millones|millón|millon|lucas|luca|palos|palo|mil|k)?",
    re.IGNORECASE,
)

_LEADING_PREP = re.compile(
    r"^(?:en|de|del|para|por|una?\s+|de\s+una?\s+)\s*", re.IGNORECASE
)
_TRAILING_PREP = re.compile(
    r"\s+(?:en|de|del|para|por|una?|de\s+una?)$", re.IGNORECASE
)


def _clean_source(text: str) -> str:
    text = text.strip(" .,;:-–—")
    text = _LEADING_PREP.sub("", text)
    text = _TRAILING_PREP.sub("", text)
    return text.strip()


def _strip_verbs(text: str) -> str:
    for v in _INCOME_VERBS:
        if text.lower().startswith(v):
            return text[len(v):].strip()
    return text


def parse_income(text: str) -> dict:
    """Parsea texto libre a un ingreso estructurado.

    Returns dict: amount (int CLP), source_text (str), kind ('income'), raw (str).
    Lanza ParseError si no hay monto válido.
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

    after = _clean_source(t[m.end():])
    source = after or _clean_source(_strip_verbs(t[: m.start()])) or "otros"

    return {"amount": amount, "source_text": source, "kind": "income", "raw": raw}
