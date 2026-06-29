# Income Tracking — Design Spec

**Date:** 2026-06-29  
**Branch:** redesign  
**Status:** approved

## Context

Fortunia tracks expenses (boletas via OCR + texto libre). Without income data, there is nothing to contrast expenses against. This spec adds income registration, storage, and dashboard display.

## Scope

1. New `incomes` table + income categories in `categories` (classification='income')
2. `text_income.py` — deterministic free-text income parser (no LLM)
3. `POST /income` endpoint in worker
4. `categorize_income()` function + income aliases in `item_aliases`
5. Dashboard redesign: income bar (data-driven) + balance + expense section below
6. Unit tests for parser
7. Playwright end-to-end verification

Out of scope: multi-user income tracking, income editing/deletion UI, CSV import.

---

## 1. Database Schema

### New table: `incomes`

```sql
CREATE TABLE IF NOT EXISTS incomes (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id BIGINT REFERENCES categories(id),
  amount      NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  source_text TEXT,        -- normalized source extracted from text ("sueldo", "guitarra")
  raw_text    TEXT,        -- original input text verbatim
  issued_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incomes_date ON incomes (issued_date);
```

### Income categories (seed in `categories`)

Insert with `classification = 'income'`, `parent_id = NULL` (top-level):

| name | classification |
|------|---------------|
| Laboral | income |
| Ventas | income |
| Arriendo | income |
| Freelance | income |
| Otros ingresos | income |

### Income aliases (seed in `item_aliases`)

Map source keywords → income category_id:

| pattern | match_type | category |
|---------|-----------|---------|
| sueldo | contains | Laboral |
| salario | contains | Laboral |
| bono | contains | Laboral |
| comisión / comision | contains | Laboral |
| venta | contains | Ventas |
| vendí / vendi | contains | Ventas |
| arriendo | contains | Arriendo |
| arrienda | contains | Arriendo |
| freelance | contains | Freelance |
| consultoría | contains | Freelance |

### Analytical view

```sql
CREATE OR REPLACE VIEW v_monthly_income_by_category AS
SELECT
  date_trunc('month', issued_date)::date AS month,
  COALESCE(c.name, 'Sin categoría')      AS category,
  SUM(amount)                            AS total
FROM incomes i
LEFT JOIN categories c ON c.id = i.category_id
WHERE i.deleted_at IS NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;
```

---

## 2. Worker — Income Parser (`text_income.py`)

Mirrors `text_expense.py` exactly. Pure function, no DB, fully testable.

**Income verbs recognized:**
```
cobré, cobre, recibí, recibi, gané, gane, vendí, vendi,
ingresé, ingrese, me pagaron, cobro, sueldo, bono, arriendo
```

**Return shape:**
```python
{"amount": int, "source_text": str, "kind": "income", "raw": str}
```

**Rules:**
- Same amount regex + CLP multipliers (mil, k, luca, palo, millón) as `text_expense.py`
- `source_text` = text after amount (stripped of leading prepositions), or text before amount stripped of income verb, or "otros"
- `MAX_AMOUNT = 1_000_000_000` (same ceiling)
- Raises `ParseError` (same class from `text_expense.py`) for: empty text, no amount found, amount ≤ 0, amount > MAX

---

## 3. Worker — Categorization (`categorize.py`)

New function `categorize_income(source_text: str) -> tuple[int|None, str|None, str]`.

Queries `item_aliases` joined to `categories WHERE classification='income'`. Falls back to `category_id` of "Otros ingresos" if no alias matches. Returns `(category_id, normalized_name, source)` matching the existing `categorize()` signature.

---

## 4. Worker — Persistence (`db.py`)

New function `persist_income(parsed: dict, category_id: int|None) -> tuple[int, bool]`:

```python
INSERT INTO incomes (category_id, amount, source_text, raw_text, issued_date)
VALUES (...)
RETURNING id
```

No idempotency key for incomes (two identical salaries on different dates are valid). Returns `(income_id, True)` always.

---

## 5. Worker — Endpoint (`app.py`)

```python
class TextIncome(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)

@app.post("/income")
def income_text(payload: TextIncome) -> dict:
    """Registra ingreso desde texto libre ("cobré 5.000.000 de sueldo")."""
    try:
        parsed = parse_income(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    cat_id, norm, source = categorize_income(parsed["source_text"])
    income_id, _ = persist_income(parsed, cat_id)
    return {
        "income_id": income_id,
        "amount": parsed["amount"],
        "source_text": parsed["source_text"],
        "category_id": cat_id,
        "category": norm or parsed["source_text"],
        "issued_date": str(date.today()),
    }
```

---

## 6. Dashboard Redesign

### New queries (`dashboard/queries.py`)

```python
def income_kpis(month: str) -> dict:
    # Returns: {total, count}

def income_by_category(month: str) -> list[dict]:
    # Returns only categories with SUM > 0 for the month
    # [{category, total}, ...] ordered by total DESC

def months_available() -> list[str]:
    # Updated: UNION receipts + incomes dates
```

### New template: `_income_bar.html`

- Green-accented article card (full width)
- Header: "Ingresos del mes" + total formateado CLP
- Stacked horizontal bar (Chart.js) — one segment per category returned by `income_by_category`
- If no incomes for month: muestra "Sin ingresos registrados este mes"
- Data-driven: template iterates whatever categories arrive, zero hardcode

### Updated `_overview.html`

Layout order (top → bottom):

1. `_income_bar.html` (include)
2. Balance card (full width): Ingresos / Gastos / Ahorro % + horizontal progress bar (green=income used, red=expenses)
3. KPIs actuales (total gasto, boletas, ítems)
4. Grid 2-col: donut categorías gasto + tabla categorías
5. Grid 2-col: top comercios + boletas recientes

### Updated `base.html`

Nav gains link: `Ingresos → /incomes`

### New page: `/incomes` + `incomes.html`

List of income entries for selected month. Columns: Fecha, Fuente, Categoría, Monto. Analogous to `/expenses`.

---

## 7. Tests

### `worker/tests/test_text_income.py`

| test | input | expected |
|------|-------|---------|
| sueldo básico | "cobré 5.000.000 de sueldo" | amount=5_000_000, source="sueldo" |
| venta objeto | "vendí una guitarra por 350.000" | amount=350_000, source="guitarra" |
| bono con multiplicador | "recibí 200 mil de bono" | amount=200_000, source="bono" |
| palo slang | "me pagaron 1 palo" | amount=1_000_000 |
| millones | "gané 2 millones freelance" | amount=2_000_000, source="freelance" |
| sin monto | "hola como estas" | ParseError |
| vacío | "" | ParseError |
| cero | "cobré 0 de sueldo" | ParseError |
| excesivo | "cobré 9999999999999" | ParseError |
| kind siempre income | "cobré 1000" | kind="income" |

---

## 8. Playwright Verification

Script `scripts/verify_income.py` (or inline pytest with playwright):

1. POST `worker:8000/income` body `{"text": "cobré 5.000.000 de sueldo"}` → assert 200, `income_id` present
2. POST `worker:8000/income` body `{"text": "vendí guitarra por 350.000"}` → assert 200
3. Navigate `http://localhost:8001/` (dashboard)
4. Assert income bar visible with `$5.350.000`
5. Assert "Laboral" row present
6. Assert "Ventas" row present (second income triggered second category)
7. Assert balance section shows Ingresos > Gastos
8. Navigate `/incomes` → assert 2 rows in table

---

## Architecture Notes

- `text_income.py` is a pure function — import `ParseError` from `text_expense.py` (no duplication)
- `categorize_income()` queries same `item_aliases` table but filters `categories.classification='income'`
- Dashboard `fortunia_ro` role has SELECT on `incomes` — add GRANT in migration
- Migration file: `db/05_incomes.sql`
