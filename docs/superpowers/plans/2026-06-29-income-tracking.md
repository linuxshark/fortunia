# Income Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add income registration (text-based), storage, and dashboard display to Fortunia so expenses can be contrasted against real income.

**Architecture:** New `incomes` table with `category_id` referencing `categories(classification='income')`. Worker gains `POST /income` backed by a deterministic text parser mirroring `text_expense.py`. Dashboard gains an income bar (data-driven, renders only categories with data) above a balance card, then existing expense sections below.

**Tech Stack:** Python 3.11, FastAPI, psycopg3, PostgreSQL 16, Jinja2, Chart.js, HTMX, Pico CSS, pytest.

## Global Constraints

- CLP amounts are integers — no decimals, dot is thousands separator.
- `ParseError` is defined in `text_expense.py` — import from there, do not duplicate.
- `categorize_income()` passes the **full raw text** (not just source_text) to match verb-based aliases ("vendí", "sueldo").
- `fortunia_ro` role: run `make ro-role` after every migration; the role script uses `GRANT SELECT ON ALL TABLES` so new tables/views are covered automatically.
- Worker exposed on host port **8002** (`http://localhost:8002`). Dashboard on **8001** (`http://localhost:8001`).
- Run tests from `worker/` directory: `cd worker && python -m pytest tests/test_text_income.py -v`
- All templates use `{{ value | clp }}` for CLP formatting.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `db/05_incomes.sql` | Migration: incomes table, income categories, income aliases, view |
| Create | `worker/text_income.py` | Deterministic income text parser |
| Create | `worker/tests/test_text_income.py` | Unit tests for parser |
| Modify | `worker/categorize.py` | Add `categorize_income()`, refactor `_QUERY` to filter by classification |
| Modify | `worker/db.py` | Add `persist_income()` |
| Modify | `worker/app.py` | Add `POST /income` endpoint |
| Modify | `dashboard/queries.py` | Add `income_kpis()`, `income_by_category()`, `recent_incomes()`, update `months_available()` |
| Modify | `dashboard/app.py` | Update `_overview_ctx()`, add `/incomes` route |
| Create | `dashboard/templates/_income_bar.html` | Income stacked bar partial |
| Modify | `dashboard/templates/_overview.html` | Full rewrite: income bar + balance + expenses |
| Modify | `dashboard/templates/base.html` | Add Ingresos nav link |
| Create | `dashboard/templates/incomes.html` | Income list page |
| Modify | `dashboard/static/styles.css` | Income bar + balance card styles |

---

### Task 1: DB Migration

**Files:**
- Create: `db/05_incomes.sql`

**Interfaces:**
- Produces: `incomes` table, income categories (IDs auto-assigned after 13), `v_monthly_income_by_category` view, income aliases in `item_aliases`

- [ ] **Step 1: Write the migration file**

```sql
-- db/05_incomes.sql
-- Income categories (classification='income', parent_id=NULL — top-level)
INSERT INTO categories (name, classification) VALUES
  ('Laboral',        'income'),
  ('Ventas',         'income'),
  ('Arriendo',       'income'),
  ('Freelance',      'income'),
  ('Otros ingresos', 'income')
ON CONFLICT DO NOTHING;

-- Income aliases: matched against the full raw income text (ILIKE, case-insensitive)
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority) VALUES
  ('sueldo',      'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('salario',     'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('bono',        'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('comision',    'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 20),
  ('comisión',    'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 20),
  ('vendi',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('vendí',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('venta',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('arriendo',    'contains', 'Arriendo',        (SELECT id FROM categories WHERE name='Arriendo'       AND classification='income'), 10),
  ('arrienda',    'contains', 'Arriendo',        (SELECT id FROM categories WHERE name='Arriendo'       AND classification='income'), 10),
  ('freelance',   'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10),
  ('consultoria', 'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10),
  ('consultoría', 'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10)
ON CONFLICT DO NOTHING;

-- Incomes table
CREATE TABLE IF NOT EXISTS incomes (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id BIGINT REFERENCES categories(id),
  amount      NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  source_text TEXT,        -- normalized source extracted from text ("sueldo", "guitarra")
  raw_text    TEXT,        -- original input verbatim
  issued_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incomes_date ON incomes (issued_date);

-- Analytical view: monthly income by category (only rows with data)
CREATE OR REPLACE VIEW v_monthly_income_by_category AS
SELECT
  date_trunc('month', issued_date)::date       AS month,
  COALESCE(c.name, 'Sin categoría')            AS category,
  SUM(i.amount)                                AS total
FROM incomes i
LEFT JOIN categories c ON c.id = i.category_id
WHERE i.deleted_at IS NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;
```

- [ ] **Step 2: Apply migration to the running DB**

```bash
# From the project root (fortunia/):
docker compose exec -T postgres psql \
  -U "${POSTGRES_USER:-boleta}" \
  -d "${POSTGRES_DB:-boletas}" \
  < db/05_incomes.sql
```

Expected output: `INSERT 0 5`, `INSERT 0 13`, `CREATE TABLE`, `CREATE INDEX`, `CREATE VIEW`

- [ ] **Step 3: Refresh fortunia_ro grants**

```bash
make ro-role
```

Expected output: `✓ Rol fortunia_ro listo (SELECT-only sobre boletas)`

- [ ] **Step 4: Verify migration**

```bash
docker compose exec postgres psql \
  -U "${POSTGRES_USER:-boleta}" \
  -d "${POSTGRES_DB:-boletas}" \
  -c "SELECT name, classification FROM categories WHERE classification='income';"
```

Expected: 5 rows (Laboral, Ventas, Arriendo, Freelance, Otros ingresos)

```bash
docker compose exec postgres psql \
  -U "${POSTGRES_USER:-boleta}" \
  -d "${POSTGRES_DB:-boletas}" \
  -c "\d incomes"
```

Expected: table with id, category_id, amount, source_text, raw_text, issued_date, created_at, deleted_at

- [ ] **Step 5: Commit**

```bash
git add db/05_incomes.sql
git commit -m "feat(db): add incomes table, income categories, aliases, and monthly view"
```

---

### Task 2: Income Text Parser (TDD)

**Files:**
- Create: `worker/tests/test_text_income.py`
- Create: `worker/text_income.py`

**Interfaces:**
- Consumes: `normalize.clp_to_int`, `text_expense.ParseError`
- Produces: `parse_income(text: str) -> dict` — `{amount: int, source_text: str, kind: "income", raw: str}`

- [ ] **Step 1: Write failing tests**

```python
# worker/tests/test_text_income.py
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
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd worker && python -m pytest tests/test_text_income.py -v
```

Expected: `ModuleNotFoundError: No module named 'text_income'` (all tests fail)

- [ ] **Step 3: Implement `text_income.py`**

```python
# worker/text_income.py
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
    r"(mil|millones|millón|millon|lucas|luca|palos|palo|k)?",
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
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
cd worker && python -m pytest tests/test_text_income.py -v
```

Expected: all 15 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add worker/text_income.py worker/tests/test_text_income.py
git commit -m "feat(worker): add deterministic income text parser with full test suite"
```

---

### Task 3: Extend Categorizer

**Files:**
- Modify: `worker/categorize.py`

**Interfaces:**
- Consumes: existing `item_aliases` + `categories` tables (joined by classification)
- Produces: `categorize_income(raw_text: str) -> tuple[int|None, str|None, str]`
  - same signature as `categorize()`: `(category_id, normalized_name, source)`
  - **Pass the full raw income text** — not just source_text — to match verb aliases

- [ ] **Step 1: Rewrite `categorize.py`**

Replace the entire file:

```python
# worker/categorize.py
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
```

- [ ] **Step 2: Verify existing expense tests still pass**

```bash
cd worker && python -m pytest tests/test_text_expense.py tests/test_rut.py -v
```

Expected: all tests PASSED (categorize.py is not directly unit-tested; smoke via running tests is sufficient here)

- [ ] **Step 3: Commit**

```bash
git add worker/categorize.py
git commit -m "refactor(worker): filter item_aliases by category classification, add categorize_income()"
```

---

### Task 4: Extend DB Layer

**Files:**
- Modify: `worker/db.py`

**Interfaces:**
- Consumes: `incomes` table (from Task 1)
- Produces: `persist_income(parsed: dict, category_id: int|None) -> tuple[int, bool]`
  - `parsed` keys used: `amount`, `source_text`, `raw`
  - Returns `(income_id, True)` — no idempotency key, duplicate incomes on different days are valid

- [ ] **Step 1: Add `persist_income()` to `worker/db.py`**

Append after the existing `persist()` function (do not modify `persist()`):

```python
def persist_income(parsed: dict, category_id: int | None) -> tuple[int, bool]:
    """Insert a row into incomes. No idempotency — same income on different days is valid."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO incomes (category_id, amount, source_text, raw_text, issued_date)
            VALUES (%(category_id)s, %(amount)s, %(source_text)s, %(raw_text)s, CURRENT_DATE)
            RETURNING id
            """,
            {
                "category_id": category_id,
                "amount": parsed["amount"],
                "source_text": parsed["source_text"],
                "raw_text": parsed["raw"],
            },
        )
        income_id = cur.fetchone()["id"]
        conn.commit()
    return income_id, True
```

- [ ] **Step 2: Commit**

```bash
git add worker/db.py
git commit -m "feat(worker): add persist_income() to db layer"
```

---

### Task 5: POST /income Endpoint

**Files:**
- Modify: `worker/app.py`

**Interfaces:**
- Consumes: `parse_income` (Task 2), `categorize_income` (Task 3), `db.persist_income` (Task 4)
- Produces: `POST /income` → `{status, income_id, amount, source_text, category_id, category, category_source, issued_date}`

- [ ] **Step 1: Add imports and endpoint to `worker/app.py`**

Add imports at the top (after existing imports):

```python
from categorize import categorize, categorize_income
from text_income import parse_income
```

Replace the existing import line `from categorize import categorize` with the combined import above. Then add the new model and endpoint after the existing `/text` endpoint:

```python
class TextIncome(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


@app.post("/income")
def income_text(payload: TextIncome) -> dict:
    """Registra ingreso desde texto libre ("cobré 5.000.000 de sueldo").

    Parsea monto + fuente, categoriza contra aliases de ingresos,
    persiste en tabla incomes. Sin paso por OCR.
    """
    try:
        parsed = parse_income(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Pass full raw text — verb-based aliases (vendí, sueldo) need it
    cat_id, norm, source = categorize_income(parsed["raw"])
    income_id, _ = db.persist_income(parsed, cat_id)
    return {
        "status": "stored",
        "income_id": income_id,
        "amount": parsed["amount"],
        "source_text": parsed["source_text"],
        "category_id": cat_id,
        "category": norm or parsed["source_text"],
        "category_source": source,
        "issued_date": str(date.today()),
    }
```

- [ ] **Step 2: Rebuild worker container**

```bash
docker compose build worker && docker compose up -d worker
make wait-ready
```

Expected: `✓ Worker listo: {"ok":true,"db":true}`

- [ ] **Step 3: Smoke test POST /income**

```bash
curl -s -X POST http://localhost:8002/income \
  -H "Content-Type: application/json" \
  -d '{"text": "cobré 5.000.000 de sueldo"}' | python3 -m json.tool
```

Expected response (income_id will vary):
```json
{
  "status": "stored",
  "income_id": 1,
  "amount": 5000000,
  "source_text": "sueldo",
  "category_id": <laboral_id>,
  "category": "Laboral",
  "category_source": "rule",
  "issued_date": "2026-06-29"
}
```

```bash
curl -s -X POST http://localhost:8002/income \
  -H "Content-Type: application/json" \
  -d '{"text": "vendí guitarra por 350.000"}' | python3 -m json.tool
```

Expected: `"category": "Ventas"` (vendí alias triggers Ventas)

- [ ] **Step 4: Smoke test error case**

```bash
curl -s -X POST http://localhost:8002/income \
  -H "Content-Type: application/json" \
  -d '{"text": "hola como estas"}' | python3 -m json.tool
```

Expected: HTTP 422 with `"detail": "no se encontró un monto en el texto"`

- [ ] **Step 5: Commit**

```bash
git add worker/app.py
git commit -m "feat(worker): add POST /income endpoint for free-text income registration"
```

---

### Task 6: Dashboard Queries + Routes

**Files:**
- Modify: `dashboard/queries.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Produces (queries.py):
  - `income_kpis(month: str) -> dict` — `{total: Decimal, count: int}`
  - `income_by_category(month: str) -> list[dict]` — `[{category: str, total: Decimal}]` ordered by total DESC, only rows with data
  - `recent_incomes(month: str, limit: int = 25) -> list[dict]` — `[{id, issued_date, source_text, category, amount}]`
  - `months_available() -> list[str]` — updated to UNION receipts + incomes dates
- Produces (app.py):
  - `_overview_ctx` gains: `income_kpis`, `income_categories`, `income_chart_labels`, `income_chart_data`, `balance_pct`
  - New route `GET /incomes` renders `incomes.html`

- [ ] **Step 1: Add income queries to `dashboard/queries.py`**

Replace the existing `months_available()` function and append new functions after `line_items_filter()`:

Replace `months_available()`:
```python
def months_available() -> list[str]:
    sql = """
        SELECT DISTINCT m FROM (
            SELECT to_char(date_trunc('month', COALESCE(issued_date, created_at::date)), 'YYYY-MM') AS m
            FROM receipts WHERE deleted_at IS NULL
            UNION
            SELECT to_char(date_trunc('month', issued_date), 'YYYY-MM') AS m
            FROM incomes WHERE deleted_at IS NULL
        ) sub
        ORDER BY m DESC
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [r["m"] for r in cur.fetchall()]
```

Append after `line_items_filter()`:
```python
def income_kpis(month: str) -> dict:
    sql = """
        SELECT
          COALESCE(SUM(amount), 0) AS total,
          COUNT(*)                 AS count
        FROM incomes
        WHERE deleted_at IS NULL
          AND to_char(issued_date, 'YYYY-MM') = %(m)s
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month})
        return cur.fetchone() or {"total": 0, "count": 0}


def income_by_category(month: str) -> list[dict]:
    sql = """
        SELECT COALESCE(c.name, 'Sin categoría') AS category,
               SUM(i.amount)                      AS total
        FROM incomes i
        LEFT JOIN categories c ON c.id = i.category_id
        WHERE i.deleted_at IS NULL
          AND to_char(i.issued_date, 'YYYY-MM') = %(m)s
        GROUP BY 1
        HAVING SUM(i.amount) > 0
        ORDER BY 2 DESC
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month})
        return cur.fetchall()


def recent_incomes(month: str, limit: int = 25) -> list[dict]:
    sql = """
        SELECT i.id, i.issued_date, i.source_text,
               COALESCE(c.name, 'Sin categoría') AS category,
               i.amount
        FROM incomes i
        LEFT JOIN categories c ON c.id = i.category_id
        WHERE i.deleted_at IS NULL
          AND to_char(i.issued_date, 'YYYY-MM') = %(m)s
        ORDER BY i.issued_date DESC, i.id DESC
        LIMIT %(lim)s
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month, "lim": limit})
        return cur.fetchall()
```

- [ ] **Step 2: Update `_overview_ctx` and add `/incomes` route in `dashboard/app.py`**

Replace `_overview_ctx`:
```python
def _overview_ctx(request: Request, month: str | None) -> dict:
    months = q.months_available()
    month = resolve_month(month, months)
    cats = q.category_breakdown(month)
    inc_kpis = q.income_kpis(month)
    inc_cats = q.income_by_category(month)
    expense_kpis = q.kpis(month)
    inc_total = float(inc_kpis["total"])
    exp_total = float(expense_kpis["total"])
    balance_pct = int(100 * exp_total / inc_total) if inc_total > 0 else 0
    return {
        "request": request,
        "month": month,
        "months": months,
        "kpis": expense_kpis,
        "income_kpis": inc_kpis,
        "income_categories": inc_cats,
        "income_chart_labels": [c["category"] for c in inc_cats],
        "income_chart_data": [float(c["total"]) for c in inc_cats],
        "balance_pct": min(balance_pct, 100),
        "categories": cats,
        "merchants": q.top_merchants(month),
        "receipts": q.recent_receipts(month),
        "chart_labels": [c["category"] for c in cats],
        "chart_data": [float(c["total"]) for c in cats],
        "chart_colors": [color_for(c["category"]) for c in cats],
    }
```

Add new route after the `expenses` route:
```python
@app.get("/incomes", response_class=HTMLResponse)
def incomes(request: Request, month: str | None = None):
    months = q.months_available()
    month = resolve_month(month, months)
    rows = q.recent_incomes(month)
    total = sum(float(r["amount"] or 0) for r in rows)
    return templates.TemplateResponse(request, "incomes.html", {
        "request": request, "month": month, "months": months,
        "rows": rows, "total": total,
    })
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/queries.py dashboard/app.py
git commit -m "feat(dashboard): add income queries, income_kpis, income_by_category, /incomes route"
```

---

### Task 7: Dashboard UI — Templates + Styles + Playwright Verification

**Files:**
- Create: `dashboard/templates/_income_bar.html`
- Modify: `dashboard/templates/_overview.html` (full rewrite)
- Modify: `dashboard/templates/base.html`
- Create: `dashboard/templates/incomes.html`
- Modify: `dashboard/static/styles.css`

**Interfaces:**
- Consumes from context: `income_kpis`, `income_categories`, `income_chart_labels`, `income_chart_data`, `balance_pct`, `kpis`, `categories`, `merchants`, `receipts`, `chart_labels`, `chart_data`, `chart_colors`

- [ ] **Step 1: Create `dashboard/templates/_income_bar.html`**

```html
{# dashboard/templates/_income_bar.html #}
<article class="income-bar">
  <header class="income-bar-header">
    <strong>Ingresos del mes</strong>
    <span class="income-total">{{ income_kpis.total | clp }}</span>
  </header>
  {% if income_categories %}
    <div class="income-chart-wrap">
      <canvas id="incomeChart"></canvas>
    </div>
    <script id="incomeData" type="application/json">
      {"labels": {{ income_chart_labels | tojson }}, "data": {{ income_chart_data | tojson }}}
    </script>
    <script>
      (function () {
        var el = document.getElementById('incomeChart');
        if (!el || !window.Chart) return;
        if (window._incomeChart) window._incomeChart.destroy();
        var d = JSON.parse(document.getElementById('incomeData').textContent);
        var palette = ['#16a34a', '#0891b2', '#7c3aed', '#ca8a04', '#db2777'];
        window._incomeChart = new Chart(el, {
          type: 'bar',
          data: {
            labels: [''],
            datasets: d.labels.map(function (lbl, i) {
              return {
                label: lbl,
                data: [d.data[i]],
                backgroundColor: palette[i % palette.length],
                borderWidth: 0
              };
            })
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'right' },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    return ' $' + Math.round(ctx.parsed.x).toLocaleString('es-CL');
                  }
                }
              }
            },
            scales: {
              x: { stacked: true, display: false },
              y: { stacked: true, display: false }
            }
          }
        });
      })();
    </script>
    <table class="income-table">
      <tbody>
        {% for c in income_categories %}
        <tr>
          <td>{{ c.category }}</td>
          <td class="num">{{ c.total | clp }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="muted">Sin ingresos registrados este mes.</p>
  {% endif %}
</article>
```

- [ ] **Step 2: Rewrite `dashboard/templates/_overview.html`**

Replace the entire file:

```html
{# dashboard/templates/_overview.html #}

{# 1. Income bar — data-driven, only renders categories with data #}
{% include "_income_bar.html" %}

{# 2. Balance card #}
<article class="balance-card">
  <header><strong>Balance mensual</strong></header>
  <div class="balance-grid">
    <div class="balance-item income-side">
      <small class="muted">Ingresos</small>
      <strong>{{ income_kpis.total | clp }}</strong>
    </div>
    <div class="balance-item expense-side">
      <small class="muted">Gastos</small>
      <strong>{{ kpis.total | clp }}</strong>
    </div>
    <div class="balance-item">
      <small class="muted">Ahorro</small>
      <strong>{{ (100 - balance_pct) }}%</strong>
    </div>
  </div>
  <div class="balance-bar-wrap" title="Gastos vs Ingresos">
    <div class="balance-bar-fill" style="width: {{ balance_pct }}%"></div>
  </div>
</article>

{# 3. KPIs — expense summary #}
<section class="kpis grid">
  <article class="kpi">
    <small class="muted">Total gastos mes</small>
    <h2>{{ kpis.total | clp }}</h2>
  </article>
  <article class="kpi">
    <small class="muted">Boletas</small>
    <h2>{{ kpis.receipts }}</h2>
  </article>
  <article class="kpi">
    <small class="muted">Ítems</small>
    <h2>{{ kpis['items'] }}</h2>
  </article>
</section>

{# 4. Category chart + table #}
<div class="grid cols-2">
  <article>
    <header><strong>Gasto por categoría</strong></header>
    {% if categories %}
      <div class="chart-wrap"><canvas id="catChart"></canvas></div>
      <script id="catData" type="application/json">
        {"labels": {{ chart_labels | tojson }}, "data": {{ chart_data | tojson }}, "colors": {{ chart_colors | tojson }}}
      </script>
      <script>
        (function () {
          var el = document.getElementById('catChart');
          if (!el || !window.Chart) return;
          if (window._catChart) window._catChart.destroy();
          var d = JSON.parse(document.getElementById('catData').textContent);
          window._catChart = new Chart(el, {
            type: 'doughnut',
            data: { labels: d.labels, datasets: [{ data: d.data, backgroundColor: d.colors, borderWidth: 1 }] },
            options: {
              plugins: { legend: { position: 'right' } },
              responsive: true, maintainAspectRatio: false, cutout: '58%'
            }
          });
        })();
      </script>
    {% else %}
      <p class="muted">Sin datos para este mes.</p>
    {% endif %}
  </article>

  <article>
    <header><strong>Categorías</strong></header>
    <table>
      <thead><tr><th>Categoría</th><th class="num">Total</th></tr></thead>
      <tbody>
        {% for c in categories %}
        <tr>
          <td><span class="dot" style="background:{{ color_for(c.category) }}"></span>
            <a href="/category/{{ c.category }}?month={{ month }}">{{ c.category }}</a></td>
          <td class="num">{{ c.total | clp }}</td>
        </tr>
        {% else %}
        <tr><td colspan="2" class="muted">—</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </article>
</div>

{# 5. Top merchants + recent receipts #}
<div class="grid cols-2">
  <article>
    <header><strong>Top comercios</strong></header>
    <table>
      <thead><tr><th>Comercio</th><th class="num">Total</th></tr></thead>
      <tbody>
        {% for m in merchants %}
        <tr><td>{{ m.merchant }}</td><td class="num">{{ m.total | clp }}</td></tr>
        {% else %}
        <tr><td colspan="2" class="muted">—</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </article>

  <article>
    <header><strong>Boletas recientes</strong></header>
    <table>
      <thead><tr><th>Fecha</th><th>Comercio</th><th class="num">Ítems</th><th class="num">Total</th></tr></thead>
      <tbody>
        {% for r in receipts %}
        <tr>
          <td>{{ r.issued_date }}</td>
          <td><a href="/receipt/{{ r.id }}">{{ r.merchant }}</a></td>
          <td class="num">{{ r['items'] }}</td>
          <td class="num">{{ r.total | clp }}</td>
        </tr>
        {% else %}
        <tr><td colspan="4" class="muted">Sin boletas este mes.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </article>
</div>
```

- [ ] **Step 3: Update `dashboard/templates/base.html` — add Ingresos nav link**

In the nav `<ul>` on the right, add the Ingresos link after Gastos:

```html
      <li><a href="/">Resumen</a></li>
      <li><a href="/expenses">Gastos</a></li>
      <li><a href="/incomes">Ingresos</a></li>
```

- [ ] **Step 4: Create `dashboard/templates/incomes.html`**

```html
{# dashboard/templates/incomes.html #}
{% extends "base.html" %}
{% block title %}fortunia · ingresos{% endblock %}
{% block content %}
<header class="page-head">
  <hgroup>
    <h1>Ingresos</h1>
    <p class="muted">Total del mes: {{ total | clp }}</p>
  </hgroup>
  <form class="month-form" hx-get="/incomes" hx-target="body" hx-push-url="true"
        hx-trigger="change from:select">
    <select name="month" aria-label="Mes">
      {% for m in months %}
        <option value="{{ m }}" {% if m == month %}selected{% endif %}>{{ m }}</option>
      {% endfor %}
      {% if month not in months %}<option value="{{ month }}" selected>{{ month }}</option>{% endif %}
    </select>
  </form>
</header>

<article>
  <table>
    <thead>
      <tr>
        <th>Fecha</th>
        <th>Fuente</th>
        <th>Categoría</th>
        <th class="num">Monto</th>
      </tr>
    </thead>
    <tbody>
      {% for r in rows %}
      <tr>
        <td>{{ r.issued_date }}</td>
        <td>{{ r.source_text or '—' }}</td>
        <td>{{ r.category }}</td>
        <td class="num">{{ r.amount | clp }}</td>
      </tr>
      {% else %}
      <tr><td colspan="4" class="muted">Sin ingresos registrados este mes.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</article>
{% endblock %}
```

- [ ] **Step 5: Add income styles to `dashboard/static/styles.css`**

Append to end of file:

```css
/* Income bar */
.income-bar { border-left: 4px solid #16a34a; margin-bottom: 1rem; }
.income-bar-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: .5rem;
}
.income-total { font-size: 1.4rem; font-weight: 700; color: #16a34a; }
.income-chart-wrap { position: relative; height: 56px; margin: .5rem 0; }
.income-table { margin-top: .5rem; }
.income-table td { padding: .25rem .5rem; }

/* Balance card */
.balance-card { margin-bottom: 1.5rem; }
.balance-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 1rem; margin-bottom: .75rem; text-align: center;
}
.balance-item { display: flex; flex-direction: column; gap: .2rem; }
.income-side strong { color: #16a34a; font-size: 1.1rem; }
.expense-side strong { color: #dc2626; font-size: 1.1rem; }
.balance-bar-wrap {
  height: 10px; background: #16a34a; border-radius: 5px; overflow: hidden;
}
.balance-bar-fill {
  height: 100%; background: #dc2626; border-radius: 5px;
  transition: width .4s ease; min-width: 0;
}
```

- [ ] **Step 6: Rebuild dashboard**

```bash
docker compose build dashboard && docker compose up -d dashboard
make wait-dashboard
```

Expected: `✓ Dashboard listo`

- [ ] **Step 7: Playwright verification**

Use Playwright browser tools (available in this session) to verify end-to-end:

**7a. POST two incomes via worker API:**
```bash
curl -s -X POST http://localhost:8002/income \
  -H "Content-Type: application/json" \
  -d '{"text": "cobré 5.000.000 de sueldo"}' | python3 -m json.tool

curl -s -X POST http://localhost:8002/income \
  -H "Content-Type: application/json" \
  -d '{"text": "vendí guitarra por 350.000"}' | python3 -m json.tool
```

Both must return `"status": "stored"`.

**7b. Navigate dashboard and verify income bar:**

Open `http://localhost:8001/` in Playwright browser. Assert:
- Income bar article visible with `$5.350.000` total
- "Laboral" row visible in income table
- "Ventas" row visible in income table (second income triggered it)
- Balance card shows Ingresos > Gastos

**7c. Navigate /incomes and verify list:**

Open `http://localhost:8001/incomes`. Assert:
- Table has 2 rows
- Row 1: source_text "sueldo", category "Laboral", amount `$5.000.000`
- Row 2: source_text contains "guitarra", category "Ventas"

**7d. Verify "Sin ingresos" state:**

Select a month with no incomes. Assert income bar shows `Sin ingresos registrados este mes.`

- [ ] **Step 8: Commit**

```bash
git add dashboard/templates/_income_bar.html \
        dashboard/templates/_overview.html \
        dashboard/templates/base.html \
        dashboard/templates/incomes.html \
        dashboard/static/styles.css
git commit -m "feat(dashboard): income bar, balance card, /incomes page — dashboard redesign complete"
```

---

## Self-Review

**Spec coverage:**
- ✅ `POST /income` endpoint — Task 5
- ✅ Income stored in `incomes` table with `categories.classification='income'` — Tasks 1, 4
- ✅ Text parser with income verbs — Task 2
- ✅ Dashboard income bar (data-driven) — Task 7
- ✅ Balance section (income vs expenses) — Task 7
- ✅ Unit tests for `parse_income` — Task 2
- ✅ Playwright verification — Task 7 step 7
- ✅ `months_available()` unified — Task 6
- ✅ `/incomes` list page — Tasks 6, 7
- ✅ `fortunia_ro` grant — Task 1 step 3

**Type consistency:**
- `parse_income` returns `{amount: int, source_text: str, kind: "income", raw: str}` — used consistently in Tasks 2, 5
- `categorize_income(raw_text: str)` receives `parsed["raw"]` in Task 5 — matches signature in Task 3
- `persist_income(parsed, category_id)` receives `parsed` dict + `cat_id` — matches signature in Tasks 4, 5
- `income_kpis`, `income_by_category` keys (`total`, `count`, `category`) — used consistently in Tasks 6, 7

**Placeholder scan:** None found. All steps have complete code.
