"""Phase 4 — deterministic, no-LLM categorization via item_aliases.

See docs/04-database-schema.md. First match by priority wins; ILIKE for
contains/prefix/exact, ~* for regex. Returns (category_id, normalized_name,
source) where source is 'rule' or 'unmatched'.
"""
from __future__ import annotations

import db

_QUERY = """
SELECT category_id, normalized_name
FROM item_aliases
WHERE (match_type='contains' AND %(t)s ILIKE '%%'||pattern||'%%')
   OR (match_type='prefix'   AND %(t)s ILIKE pattern||'%%')
   OR (match_type='exact'    AND %(t)s ILIKE pattern)
   OR (match_type='regex'    AND %(t)s ~* pattern)
ORDER BY priority
LIMIT 1
"""


def categorize(raw_text: str) -> tuple[int | None, str | None, str]:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(_QUERY, {"t": raw_text})
        row = cur.fetchone()
    if row:
        return row["category_id"], row["normalized_name"], "rule"
    return None, None, "unmatched"
