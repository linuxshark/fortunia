"""Phase 4 — deterministic, no-LLM categorization via item_aliases.

See docs/04-database-schema.md. First match by priority wins; ILIKE for
contains/prefix/exact, ~* for regex. Filters by categories.classification
so income aliases never bleed into expense categorization and vice-versa.
Returns (category_id, normalized_name, source) where source is 'rule' or 'unmatched'.
"""
from __future__ import annotations

import db

_QUERY = """
SELECT ia.category_id, ia.normalized_name
FROM item_aliases ia
JOIN categories c ON c.id = ia.category_id
WHERE c.classification = %(cls)s
  AND (
    (ia.match_type = 'contains' AND %(t)s ILIKE '%%' || ia.pattern || '%%')
    OR (ia.match_type = 'prefix'   AND %(t)s ILIKE ia.pattern || '%%')
    OR (ia.match_type = 'exact'    AND %(t)s ILIKE ia.pattern)
    OR (ia.match_type = 'regex'    AND %(t)s ~* ia.pattern)
  )
ORDER BY ia.priority
LIMIT 1
"""


def _categorize(raw_text: str, classification: str) -> tuple[int | None, str | None, str]:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(_QUERY, {"t": raw_text, "cls": classification})
        row = cur.fetchone()
    if row:
        return row["category_id"], row["normalized_name"], "rule"
    return None, None, "unmatched"


def categorize(raw_text: str) -> tuple[int | None, str | None, str]:
    return _categorize(raw_text, "expense")


def categorize_income(raw_text: str) -> tuple[int | None, str | None, str]:
    """Categorize income text. Pass the full raw input (verb-based aliases need it)."""
    return _categorize(raw_text, "income")


def categorize_shared(raw_text: str) -> tuple[int | None, str | None, str]:
    """Categoriza texto contra categorías compartidas del hogar (classification='shared').

    Se usa para decidir si un gasto por texto libre debe rutear al Fondo Común
    en vez del flujo normal de gasto. Devuelve (category_id, normalized_name, source).
    """
    return _categorize(raw_text, "shared")


def resolve_shared(raw_text: str) -> tuple[int | None, str | None, str]:
    """Resuelve texto a una categoría del Fondo Común: aliases, luego nombre literal.

    Los aliases cubren el vocabulario coloquial ('bencina' → Gasolina) pero no
    garantizan el nombre de la categoría misma; escribir "gasté X en alimentos"
    caía al flujo de boleta de texto porque 'alimentos' no era alias. El fallback
    por nombre hace que TODA categoría compartida sea direccionable por texto,
    incluidas las que se agreguen después. source: 'rule' | 'name' | 'unmatched'.
    """
    cat_id, norm, source = categorize_shared(raw_text)
    if cat_id is not None:
        return cat_id, norm, source

    cat_id = db.shared_category_id_by_name(raw_text)
    if cat_id is not None:
        return cat_id, db.shared_category_name(cat_id), "name"
    return None, None, "unmatched"
