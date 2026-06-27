"""Normalization helpers — RUT mod-11, CLP amounts, Spanish dates.

CLP has no decimals and uses dot as thousands separator, so amounts reduce to
integers. Date parsing uses dateparser when available, else a DMY regex fallback
so the core stays testable without the dependency. All offline, token-free.
"""
from __future__ import annotations

import re
from datetime import date

# ---------------- RUT (mod-11) ----------------

def clean_rut(rut: str) -> str:
    if not rut:
        return ""
    return re.sub(r"[.\-\s]", "", rut).upper()


def rut_check_digit(body: str) -> str:
    total, factor = 0, 2
    for ch in reversed(body):
        total += int(ch) * factor
        factor = 2 if factor == 7 else factor + 1
    rem = 11 - (total % 11)
    return {11: "0", 10: "K"}.get(rem, str(rem))


def validate_rut(rut: str) -> bool:
    cleaned = clean_rut(rut)
    if len(cleaned) < 2 or not cleaned[:-1].isdigit():
        return False
    body, dv = cleaned[:-1], cleaned[-1]
    return rut_check_digit(body) == dv


def format_rut(rut: str) -> str:
    """Canonical 'XX.XXX.XXX-D' from any cleaned/raw form."""
    c = clean_rut(rut)
    body, dv = c[:-1], c[-1]
    parts = []
    while len(body) > 3:
        parts.insert(0, body[-3:])
        body = body[:-3]
    parts.insert(0, body)
    return ".".join(parts) + "-" + dv


# ---------------- CLP amounts ----------------

def clp_to_int(s: str) -> int | None:
    """'$ 19.990' / '19.990' / '1.234' -> 19990 / 1234. CLP = no decimals."""
    if s is None:
        return None
    digits = re.sub(r"[^\d]", "", s)
    return int(digits) if digits else None


# ---------------- Dates ----------------

_DMY = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+de\s+([a-zA-Záéíóú]+)\s+de\s+(\d{4})\b", re.IGNORECASE)


def parse_date(s: str) -> date | None:
    """Spanish DMY date. Tries dateparser, falls back to regex (stdlib)."""
    if not s:
        return None
    try:
        import dateparser  # type: ignore
        d = dateparser.parse(
            s, languages=["es"],
            settings={"DATE_ORDER": "DMY", "STRICT_PARSING": True},
        )
        if d:
            return d.date()
    except Exception:
        pass
    m = _TEXT_DATE.search(s)
    if m:
        mon = _MONTHS.get(m.group(2).lower())
        if mon:
            try:
                return date(int(m.group(3)), mon, int(m.group(1)))
            except ValueError:
                return None
    m = _DMY.search(s)
    if m:
        d, mo, y = (int(x) for x in m.groups())
        if y < 100:
            y += 2000
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    return None
