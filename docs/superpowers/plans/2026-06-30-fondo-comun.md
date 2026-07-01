# Fondo Común — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir gestión de "Fondo Común" del hogar a Fortunia: presupuesto mensual de categorías compartidas (editable por mes), que se consume cuando los pagos se declaran por texto libre vía Telegram (worker `/text`), visualizado en el dashboard con barra de progreso y tarjetas por categoría.

**Architecture:** El dominio del fondo vive en una tabla nueva `fund_monthly` (estado presupuesto/pago por categoría y mes), aislada del flujo OCR (`receipts`/`line_items`); ambos comparten solo `categories`. El worker (rol owner, RW) escribe pagos y el dashboard (rol `fortunia_ro`, con grant acotado a `fund_monthly`) lee todo y escribe únicamente el presupuesto. La detección de "categoría compartida" reusa el motor determinista `item_aliases` filtrando por `classification='shared'`.

**Tech Stack:** Python 3.11, FastAPI, psycopg3, Jinja2 + HTMX + Chart.js, PostgreSQL 16, Docker Compose, pytest (unit + DB-integration), Playwright (pytest-playwright) para E2E.

## Global Constraints

- **Dinero como `NUMERIC(14,2)`** — nunca float. CLP sin decimales (enteros).
- **El dashboard solo escribe `fund_monthly`** — ningún otro objeto. Todo otro acceso del dashboard es `SELECT`.
- **Pago idempotente por `(category_id, month)`** — reportar de nuevo el mismo mes REEMPLAZA el monto, no suma.
- **El worker no crea `receipt`/`line_item` para pagos de categorías compartidas** (evita doble conteo con KPIs de gasto OCR).
- **`month` se almacena como `DATE` = primer día del mes**; en el dashboard el mes viaja como string `'YYYY-MM'`.
- **DDL idempotente**: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `CREATE OR REPLACE VIEW`.
- **Categorías compartidas y montos objetivo** (verbatim del doc de estrategia): Agua 30000, Electricidad 55000, Internet 30000, Supermercado 600000, Arriendo/Dividendo 800000, Jardín infantil 450000, Auto (cuota) 472000, Restaurantes 250000, Remesas Venezuela 350000, GGCC 100000, Gasolina 100000, TAG 80000, Ahorro 500000.
- **Tests DB-integration corren en el host** (`cd worker && pytest`) contra la Postgres publicada por compose en `localhost:5432`. Precondición: `make deploy` levantado. Si la DB no responde, los tests DB se auto-skipean (fixture).

---

## File Structure

**Crear:**
- `db/06_fund.sql` — schema del fondo: `categories.target_amount`, semillas shared, aliases shared, tabla `fund_monthly`, vista `v_fund_monthly`.
- `worker/tests/conftest.py` — fixture `db` (conexión owner, skip si DB caída) + helper de limpieza.
- `worker/tests/test_fund_db.py` — tests DB-integration de `categorize_shared` y `upsert_fund_payment`.
- `dashboard/writes.py` — única capa de escritura del dashboard (acotada a `fund_monthly`).
- `dashboard/templates/_fund.html` — partial: barra de progreso + tarjetas de categoría compartida.
- `e2e/conftest.py`, `e2e/test_fondo_comun.py`, `e2e/requirements.txt` — E2E Playwright.

**Modificar:**
- `db/03_ro_role.sh` — `GRANT SELECT, INSERT, UPDATE ON fund_monthly` al rol RO.
- `docker-compose.yml` — montar `05_incomes.sql` y `06_fund.sql` en `docker-entrypoint-initdb.d`.
- `worker/categorize.py` — añadir `categorize_shared`.
- `worker/db.py` — añadir `upsert_fund_payment`.
- `worker/app.py` — `/text` ramifica a fondo cuando la categoría es compartida.
- `dashboard/queries.py` — añadir `fund_status`, `fund_totals`.
- `dashboard/app.py` — emoji map, contexto de fondo en `_overview_ctx`, ruta `POST /fund/budget`.
- `dashboard/templates/_overview.html` — incluir `_fund.html`.
- `dashboard/static/styles.css` — estilos del fondo.
- `Makefile` — targets `test`, `e2e`, `fund` (aplicar DDL a DB existente).

---

## Fase A — Esquema y semilla del fondo

### Task A1: DDL del fondo (`db/06_fund.sql`) + montaje + grant

**Files:**
- Create: `db/06_fund.sql`
- Modify: `db/03_ro_role.sh`, `docker-compose.yml`, `Makefile`
- Test (verificación psql, no pytest): comandos abajo

**Interfaces:**
- Produces: tabla `fund_monthly(id, category_id, month, budget_amount, paid_amount, paid_at, source, updated_at)` con `UNIQUE(category_id, month)`; columna `categories.target_amount NUMERIC(14,2)`; categorías `classification='shared'`; aliases shared; vista `v_fund_monthly(month, category, budget_amount, paid_amount, remaining, paid)`.

- [ ] **Step 1: Escribir `db/06_fund.sql`**

```sql
-- db/06_fund.sql — Fondo Común (gasto compartido del hogar).
-- Idempotente: seguro de re-ejecutar. Ver docs/superpowers/specs/2026-06-30-fondo-comun-design.md

-- 1) Presupuesto objetivo por categoría (default mensual; override por mes en fund_monthly)
ALTER TABLE categories ADD COLUMN IF NOT EXISTS target_amount NUMERIC(14,2);

-- 2) Categorías compartidas (classification='shared'). Montos = doc de estrategia.
INSERT INTO categories (name, classification, target_amount) VALUES
  ('Agua',               'shared',  30000),
  ('Electricidad',       'shared',  55000),
  ('Internet',           'shared',  30000),
  ('Supermercado',       'shared', 600000),
  ('Arriendo/Dividendo', 'shared', 800000),
  ('Jardín infantil',    'shared', 450000),
  ('Auto (cuota)',       'shared', 472000),
  ('Restaurantes',       'shared', 250000),
  ('Remesas Venezuela',  'shared', 350000),
  ('GGCC',               'shared', 100000),
  ('Gasolina',           'shared', 100000),
  ('TAG',                'shared',  80000),
  ('Ahorro',             'shared', 500000)
ON CONFLICT DO NOTHING;

-- 3) Aliases shared (ILIKE contains). categorize._QUERY ya filtra por classification.
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority) VALUES
  ('agua',          'contains', 'Agua',               (SELECT id FROM categories WHERE name='Agua'               AND classification='shared'), 10),
  ('luz',           'contains', 'Electricidad',       (SELECT id FROM categories WHERE name='Electricidad'       AND classification='shared'), 10),
  ('electricidad',  'contains', 'Electricidad',       (SELECT id FROM categories WHERE name='Electricidad'       AND classification='shared'), 10),
  ('internet',      'contains', 'Internet',           (SELECT id FROM categories WHERE name='Internet'           AND classification='shared'), 10),
  ('wifi',          'contains', 'Internet',           (SELECT id FROM categories WHERE name='Internet'           AND classification='shared'), 10),
  ('supermercado',  'contains', 'Supermercado',       (SELECT id FROM categories WHERE name='Supermercado'       AND classification='shared'), 10),
  ('super',         'contains', 'Supermercado',       (SELECT id FROM categories WHERE name='Supermercado'       AND classification='shared'), 20),
  ('arriendo',      'contains', 'Arriendo/Dividendo', (SELECT id FROM categories WHERE name='Arriendo/Dividendo' AND classification='shared'), 10),
  ('dividendo',     'contains', 'Arriendo/Dividendo', (SELECT id FROM categories WHERE name='Arriendo/Dividendo' AND classification='shared'), 10),
  ('jardin',        'contains', 'Jardín infantil',    (SELECT id FROM categories WHERE name='Jardín infantil'    AND classification='shared'), 10),
  ('jardín',        'contains', 'Jardín infantil',    (SELECT id FROM categories WHERE name='Jardín infantil'    AND classification='shared'), 10),
  ('restaurant',    'contains', 'Restaurantes',       (SELECT id FROM categories WHERE name='Restaurantes'       AND classification='shared'), 10),
  ('restoran',      'contains', 'Restaurantes',       (SELECT id FROM categories WHERE name='Restaurantes'       AND classification='shared'), 10),
  ('remesa',        'contains', 'Remesas Venezuela',  (SELECT id FROM categories WHERE name='Remesas Venezuela'  AND classification='shared'), 10),
  ('venezuela',     'contains', 'Remesas Venezuela',  (SELECT id FROM categories WHERE name='Remesas Venezuela'  AND classification='shared'), 10),
  ('ggcc',          'contains', 'GGCC',               (SELECT id FROM categories WHERE name='GGCC'               AND classification='shared'), 10),
  ('gastos comunes','contains', 'GGCC',               (SELECT id FROM categories WHERE name='GGCC'               AND classification='shared'), 10),
  ('gasolina',      'contains', 'Gasolina',           (SELECT id FROM categories WHERE name='Gasolina'           AND classification='shared'), 10),
  ('bencina',       'contains', 'Gasolina',           (SELECT id FROM categories WHERE name='Gasolina'           AND classification='shared'), 10),
  ('combustible',   'contains', 'Gasolina',           (SELECT id FROM categories WHERE name='Gasolina'           AND classification='shared'), 10),
  ('tag',           'contains', 'TAG',                (SELECT id FROM categories WHERE name='TAG'                AND classification='shared'), 10),
  ('ahorro',        'contains', 'Ahorro',             (SELECT id FROM categories WHERE name='Ahorro'             AND classification='shared'), 10),
  ('cuota auto',    'contains', 'Auto (cuota)',       (SELECT id FROM categories WHERE name='Auto (cuota)'       AND classification='shared'), 10),
  ('cuota del auto','contains', 'Auto (cuota)',       (SELECT id FROM categories WHERE name='Auto (cuota)'       AND classification='shared'), 10)
ON CONFLICT DO NOTHING;

-- 4) Estado por categoría y mes (presupuesto editable + pago)
CREATE TABLE IF NOT EXISTS fund_monthly (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id   BIGINT NOT NULL REFERENCES categories(id),
  month         DATE   NOT NULL,                  -- primer día del mes
  budget_amount NUMERIC(14,2) NOT NULL,
  paid_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
  paid_at       TIMESTAMPTZ,
  source        TEXT,                              -- 'telegram' | 'manual'
  updated_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (category_id, month)
);
CREATE INDEX IF NOT EXISTS idx_fund_monthly_month ON fund_monthly (month);

-- 5) Vista analítica del fondo
CREATE OR REPLACE VIEW v_fund_monthly AS
SELECT fm.month,
       c.name                               AS category,
       fm.budget_amount,
       fm.paid_amount,
       (fm.budget_amount - fm.paid_amount)  AS remaining,
       (fm.paid_amount > 0)                 AS paid
FROM fund_monthly fm
JOIN categories c ON c.id = fm.category_id
WHERE c.classification = 'shared';
```

- [ ] **Step 2: Añadir el grant RW acotado en `db/03_ro_role.sh`**

En el heredoc SQL, justo después de la línea `ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${POSTGRES_RO_USER};`, añadir:

```bash
	-- Fondo Común: el dashboard escribe SOLO esta tabla (presupuesto). Resto SELECT-only.
	GRANT SELECT, INSERT, UPDATE ON fund_monthly TO ${POSTGRES_RO_USER};
```

(`fund_monthly` usa IDENTITY; no requiere grant de secuencia.) Esta línea es idempotente: re-otorgar el mismo grant no falla.

- [ ] **Step 3: Montar los `.sql` faltantes en `docker-compose.yml`**

En el servicio `postgres`, bajo `volumes:`, después de la línea de `04_text_seed.sql`, añadir:

```yaml
      - ./db/05_incomes.sql:/docker-entrypoint-initdb.d/05_incomes.sql:ro
      - ./db/06_fund.sql:/docker-entrypoint-initdb.d/06_fund.sql:ro
```

(`05_incomes.sql` existía pero no estaba montado; sin él una init fresca no crea `incomes`. Se añade junto al fondo.)

- [ ] **Step 4: Añadir target `fund` al `Makefile` (aplicar DDL a DB ya existente)**

Los scripts de `docker-entrypoint-initdb.d` solo corren en init fresca. Para una DB existente hay que aplicar el DDL a mano. Añadir antes de la sección `# ── help ──`:

```makefile
## fund: aplica el DDL del fondo (06_fund.sql) a la DB en marcha (idempotente)
.PHONY: fund
fund:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/06_fund.sql
	@$(MAKE) --no-print-directory ro-role
	@echo "✓ Fondo Común aplicado (schema + grant RW acotado)"
```

- [ ] **Step 5: Aplicar y verificar contra la DB en marcha**

Run:
```bash
make deploy        # si no está levantado
make fund
make psql <<'SQL'
SELECT name, target_amount FROM categories WHERE classification='shared' ORDER BY id;
\d fund_monthly
SELECT has_table_privilege('fortunia_ro','fund_monthly','INSERT') AS ro_can_insert;
SELECT to_regclass('public.v_fund_monthly') AS view_exists;
SQL
```
Expected: 13 categorías shared con sus montos; `fund_monthly` con columnas y `UNIQUE (category_id, month)`; `ro_can_insert = t`; `view_exists = v_fund_monthly`.

- [ ] **Step 6: Verificar idempotencia (re-ejecutar no duplica ni falla)**

Run:
```bash
make fund
make psql <<'SQL'
SELECT count(*) AS shared_cats FROM categories WHERE classification='shared';
SQL
```
Expected: `shared_cats = 13` (sin duplicados tras segunda aplicación).

- [ ] **Step 7: Commit**

```bash
git add db/06_fund.sql db/03_ro_role.sh docker-compose.yml Makefile
git commit -m "feat(db): schema Fondo Común (categories.target_amount, fund_monthly, vista, grant RW acotado)"
```

---

## Fase B — Worker: detección y ruteo de pago al fondo

### Task B1: `categorize_shared` + fixture de tests DB

**Files:**
- Modify: `worker/categorize.py`
- Create: `worker/tests/conftest.py`, `worker/tests/test_fund_db.py`

**Interfaces:**
- Consumes: `db.connect()`, `_categorize(raw_text, classification)` (ya existen en `worker/`).
- Produces: `categorize_shared(raw_text: str) -> tuple[int|None, str|None, str]` — resuelve contra `classification='shared'`; `(category_id, normalized_name, 'rule')` si matchea, `(None, None, 'unmatched')` si no.

- [ ] **Step 1: Escribir el fixture `worker/tests/conftest.py`**

```python
"""Fixtures de tests. `db` da una conexión al owner (RW) o skipea si la DB no responde.

Los tests DB-integration corren en el host contra la Postgres de compose
(localhost:5432). Precondición: `make deploy` levantado.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from config import settings  # noqa: E402


@pytest.fixture
def db():
    try:
        conn = psycopg.connect(settings.dsn, connect_timeout=2)
    except Exception:
        pytest.skip("DB no disponible — levanta con `make deploy` para tests DB")
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture
def clean_fund(db):
    """Borra filas de fund_monthly creadas por los tests (mes 2099-01)."""
    yield
    with db.cursor() as cur:
        cur.execute("DELETE FROM fund_monthly WHERE month = DATE '2099-01-01'")
```

- [ ] **Step 2: Escribir el test fallido de `categorize_shared`**

```python
# worker/tests/test_fund_db.py
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from categorize import categorize_shared  # noqa: E402


def test_categorize_shared_electricidad(db):
    cat_id, norm, source = categorize_shared("electricidad")
    assert cat_id is not None
    assert norm == "Electricidad"
    assert source == "rule"


def test_categorize_shared_luz_alias(db):
    _, norm, _ = categorize_shared("pagué la luz")
    assert norm == "Electricidad"


def test_categorize_shared_no_match(db):
    cat_id, _, source = categorize_shared("pan amasado")
    assert cat_id is None
    assert source == "unmatched"
```

- [ ] **Step 3: Correr el test → debe fallar**

Run: `cd worker && pytest tests/test_fund_db.py::test_categorize_shared_electricidad -v`
Expected: FAIL con `ImportError: cannot import name 'categorize_shared'`.

- [ ] **Step 4: Implementar `categorize_shared` en `worker/categorize.py`**

Añadir al final del archivo:

```python
def categorize_shared(raw_text: str) -> tuple[int | None, str | None, str]:
    """Categoriza texto contra categorías compartidas del hogar (classification='shared').

    Se usa para decidir si un gasto por texto libre debe rutear al Fondo Común
    en vez del flujo normal de gasto. Devuelve (category_id, normalized_name, source).
    """
    return _categorize(raw_text, "shared")
```

- [ ] **Step 5: Correr los tests → deben pasar**

Run: `cd worker && pytest tests/test_fund_db.py -v -k categorize_shared`
Expected: 3 passed (o skipped si la DB no está levantada).

- [ ] **Step 6: Commit**

```bash
git add worker/categorize.py worker/tests/conftest.py worker/tests/test_fund_db.py
git commit -m "feat(worker): categorize_shared para detectar gasto compartido del hogar"
```

### Task B2: `upsert_fund_payment` (persistencia idempotente)

**Files:**
- Modify: `worker/db.py`
- Modify: `worker/tests/test_fund_db.py`

**Interfaces:**
- Consumes: `connect()` (psycopg, dict_row), `categorize_shared` (para obtener `category_id` en los tests).
- Produces: `upsert_fund_payment(category_id: int, month: date, amount: int, source: str) -> tuple[Decimal, Decimal]` — UPSERT sobre `(category_id, month)`; setea `paid_amount = amount` (reemplaza), `paid_at = now()`, `source`; si la fila no existía, inicializa `budget_amount` desde `categories.target_amount` (o 0). Devuelve `(paid_amount, remaining)` donde `remaining = budget_amount - paid_amount`.

- [ ] **Step 1: Escribir el test fallido (incluye idempotencia)**

Añadir a `worker/tests/test_fund_db.py`:

```python
from datetime import date  # ya importado arriba

from db import upsert_fund_payment  # noqa: E402
from categorize import categorize_shared  # noqa: E402

MONTH = date(2099, 1, 1)  # mes de pruebas, limpiado por clean_fund


def test_upsert_fund_payment_inicial(db, clean_fund):
    cat_id, _, _ = categorize_shared("electricidad")
    paid, remaining = upsert_fund_payment(cat_id, MONTH, 55000, "telegram")
    assert int(paid) == 55000
    # budget default = target_amount de Electricidad (55000) -> remaining 0
    assert int(remaining) == 0


def test_upsert_fund_payment_idempotente_reemplaza(db, clean_fund):
    cat_id, _, _ = categorize_shared("electricidad")
    upsert_fund_payment(cat_id, MONTH, 55000, "telegram")
    paid, _ = upsert_fund_payment(cat_id, MONTH, 60000, "telegram")  # reportado de nuevo
    assert int(paid) == 60000  # reemplaza, NO 115000
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM fund_monthly WHERE category_id=%s AND month=%s",
            (cat_id, MONTH),
        )
        assert cur.fetchone()[0] == 1  # una sola fila
```

- [ ] **Step 2: Correr → debe fallar**

Run: `cd worker && pytest tests/test_fund_db.py::test_upsert_fund_payment_inicial -v`
Expected: FAIL con `ImportError: cannot import name 'upsert_fund_payment'`.

- [ ] **Step 3: Implementar `upsert_fund_payment` en `worker/db.py`**

Añadir al final del archivo (y `from datetime import date` no es necesario; el tipo viaja como parámetro):

```python
def upsert_fund_payment(
    category_id: int, month, amount: int, source: str
) -> tuple:
    """Registra el pago de una categoría compartida para un mes (idempotente).

    UPSERT por (category_id, month): reemplaza paid_amount (no suma). Si la fila
    no existía, inicializa budget_amount desde categories.target_amount (o 0).
    Devuelve (paid_amount, remaining) con remaining = budget_amount - paid_amount.
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fund_monthly (category_id, month, budget_amount, paid_amount, paid_at, source)
            VALUES (
                %(cat)s, %(month)s,
                COALESCE((SELECT target_amount FROM categories WHERE id = %(cat)s), 0),
                %(amount)s, now(), %(source)s
            )
            ON CONFLICT (category_id, month) DO UPDATE
              SET paid_amount = EXCLUDED.paid_amount,
                  paid_at     = now(),
                  source      = EXCLUDED.source,
                  updated_at  = now()
            RETURNING paid_amount, (budget_amount - paid_amount) AS remaining
            """,
            {"cat": category_id, "month": month, "amount": amount, "source": source},
        )
        row = cur.fetchone()
        conn.commit()
    return row["paid_amount"], row["remaining"]
```

- [ ] **Step 4: Correr → deben pasar**

Run: `cd worker && pytest tests/test_fund_db.py -v`
Expected: todos passed (o skipped sin DB).

- [ ] **Step 5: Commit**

```bash
git add worker/db.py worker/tests/test_fund_db.py
git commit -m "feat(worker): upsert_fund_payment idempotente por (categoria, mes)"
```

### Task B3: `/text` ramifica al fondo

**Files:**
- Modify: `worker/app.py`

**Interfaces:**
- Consumes: `parse_expense`, `categorize_shared`, `categorize`, `db.upsert_fund_payment`, `db.persist`.
- Produces: respuesta JSON de `/text` con campo nuevo `routed_to: 'fund' | 'expense'`; cuando es `'fund'` incluye `category`, `category_id`, `month` (`'YYYY-MM-01'`), `paid_amount`, `remaining`.

- [ ] **Step 1: Modificar el handler `text_expense` en `worker/app.py`**

Reemplazar el cuerpo de la función `text_expense` (líneas que empiezan en `try: parsed = parse_expense(...)` hasta el `return {...}` final) por:

```python
    try:
        parsed = parse_expense(payload.text)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    amount = parsed["amount"]

    # 1) ¿Es un gasto COMPARTIDO del hogar? -> ruta al Fondo Común (no crea receipt).
    shared_id, shared_norm, shared_src = categorize_shared(parsed["category_text"])
    if shared_id is not None:
        month = date.today().replace(day=1)
        paid, remaining = db.upsert_fund_payment(shared_id, month, amount, "telegram")
        return {
            "status": "stored",
            "routed_to": "fund",
            "amount": amount,
            "category_id": shared_id,
            "category": shared_norm or parsed["category_text"],
            "category_source": shared_src,
            "month": str(month),
            "paid_amount": float(paid),
            "remaining": float(remaining),
        }

    # 2) Gasto normal -> flujo de boleta de texto (receipt + 1 line_item).
    cat_id, norm, source = categorize(parsed["category_text"])

    result = {
        "merchant_name": None,
        "rut_emisor": None,
        "rut_receptor": None,
        "doc_type": "texto",
        "tipo_dte": None,
        "folio": None,
        "issued_date": date.today(),
        "net": None,
        "tax": None,
        "total": amount,
        "ted_total": None,
        "header_source": "texto",
        "validation_status": "ok",
        "source_image_path": None,
        "image_sha256": None,
        "ocr_engine": "text",
        "ocr_confidence": None,
        "ocr_raw_text": parsed["raw"],
        "line_items": [
            {
                "line_no": 1,
                "raw_text": parsed["category_text"],
                "normalized_name": norm or parsed["category_text"],
                "category_id": cat_id,
                "category_source": source,
                "qty": 1,
                "unit_price": amount,
                "line_total": amount,
            }
        ],
    }

    receipt_id, created = db.persist(result)
    return {
        "status": "stored" if created else "duplicate",
        "routed_to": "expense",
        "receipt_id": receipt_id,
        "amount": amount,
        "category_text": parsed["category_text"],
        "category_id": cat_id,
        "category": norm or parsed["category_text"],
        "category_source": source,
        "issued_date": str(result["issued_date"]),
    }
```

- [ ] **Step 2: Añadir el import de `categorize_shared`**

En `worker/app.py` línea ~15, cambiar:

```python
from categorize import categorize, categorize_income
```
por:
```python
from categorize import categorize, categorize_income, categorize_shared
```

- [ ] **Step 3: Reconstruir el worker y verificar ruteo (gasto compartido)**

Run:
```bash
make build && make restart && make wait-ready
curl -s -X POST http://localhost:8002/text -H 'Content-Type: application/json' \
  -d '{"text":"pagué 55000 de electricidad"}' | python3 -m json.tool
```
Expected: JSON con `"routed_to": "fund"`, `"category": "Electricidad"`, `"paid_amount": 55000.0`, `"remaining": 0.0`, `"month": "2026-06-01"`.

- [ ] **Step 4: Verificar ruteo (gasto normal sigue creando receipt)**

Run:
```bash
curl -s -X POST http://localhost:8002/text -H 'Content-Type: application/json' \
  -d '{"text":"gaste 8000 en cine"}' | python3 -m json.tool
```
Expected: JSON con `"routed_to": "expense"` y un `"receipt_id"`.

- [ ] **Step 5: Verificar idempotencia end-to-end (reportar de nuevo reemplaza)**

Run:
```bash
curl -s -X POST http://localhost:8002/text -H 'Content-Type: application/json' \
  -d '{"text":"pagué 60000 de luz"}' | python3 -m json.tool
make psql <<'SQL'
SELECT category, paid_amount FROM v_fund_monthly
WHERE month = date_trunc('month', CURRENT_DATE)::date AND category='Electricidad';
SQL
```
Expected: `paid_amount = 60000.00` (una sola fila — reemplazó, no sumó).

- [ ] **Step 6: Commit**

```bash
git add worker/app.py
git commit -m "feat(worker): /text rutea gasto compartido al Fondo Común (idempotente)"
```

---

## Fase C — Dashboard: lectura y barra de progreso

### Task C1: Queries de lectura del fondo

**Files:**
- Modify: `dashboard/queries.py`

**Interfaces:**
- Consumes: `connect()` (RO), patrón de mes `'YYYY-MM'`.
- Produces:
  - `fund_status(month: str) -> list[dict]` — una fila por categoría shared (aunque no tenga pago/presupuesto ese mes): claves `category_id, category, budget_amount(float), paid_amount(float), remaining(float), paid(bool)`.
  - `fund_totals(month: str) -> dict` — claves `objetivo(float), pagado(float), restante(float), pct(int 0..100)`.

- [ ] **Step 1: Implementar `fund_status` y `fund_totals` en `dashboard/queries.py`**

Añadir al final del archivo:

```python
def _month_date(month: str) -> str:
    """'YYYY-MM' -> 'YYYY-MM-01' (primer día, como se guarda fund_monthly.month)."""
    return f"{month}-01"


def fund_status(month: str) -> list[dict]:
    """Estado del fondo por categoría compartida. LEFT JOIN: muestra todas las
    categorías shared aunque no tengan fila ese mes (presupuesto = target_amount)."""
    sql = """
        SELECT c.id AS category_id,
               c.name AS category,
               COALESCE(fm.budget_amount, c.target_amount, 0)::float8 AS budget_amount,
               COALESCE(fm.paid_amount, 0)::float8                    AS paid_amount,
               (COALESCE(fm.budget_amount, c.target_amount, 0)
                 - COALESCE(fm.paid_amount, 0))::float8               AS remaining,
               (COALESCE(fm.paid_amount, 0) > 0)                      AS paid
        FROM categories c
        LEFT JOIN fund_monthly fm
          ON fm.category_id = c.id AND fm.month = %(m)s::date
        WHERE c.classification = 'shared'
        ORDER BY c.id
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": _month_date(month)})
        return cur.fetchall()


def fund_totals(month: str) -> dict:
    """Totales del fondo: objetivo (suma de presupuestos), pagado, restante y % consumido."""
    rows = fund_status(month)
    objetivo = sum(r["budget_amount"] for r in rows)
    pagado = sum(r["paid_amount"] for r in rows)
    restante = objetivo - pagado
    pct = int(round(100 * pagado / objetivo)) if objetivo > 0 else 0
    return {
        "objetivo": objetivo,
        "pagado": pagado,
        "restante": restante,
        "pct": min(pct, 100),
    }
```

- [ ] **Step 2: Verificar contra la DB en marcha**

Run:
```bash
cd dashboard && python3 -c "
import queries as q
m = q.current_month()
print('totals', q.fund_totals(m))
print('rows', len(q.fund_status(m)))
"
```
Expected: `totals {'objetivo': 3817000.0, 'pagado': <≥60000>, 'restante': ..., 'pct': ...}`; `rows 13`.

- [ ] **Step 3: Commit**

```bash
git add dashboard/queries.py
git commit -m "feat(dashboard): fund_status y fund_totals (lectura del Fondo Común)"
```

### Task C2: Partial `_fund.html` + integración en el overview

**Files:**
- Create: `dashboard/templates/_fund.html`
- Modify: `dashboard/app.py`, `dashboard/templates/_overview.html`, `dashboard/static/styles.css`

**Interfaces:**
- Consumes: `q.fund_status`, `q.fund_totals`; filtro Jinja `clp`; global `emoji_for`.
- Produces: contexto de `_overview_ctx` con claves `fund_rows`, `fund_totals`; global de template `emoji_for(name) -> str`.

- [ ] **Step 1: Añadir el emoji map y exponerlo como global en `dashboard/app.py`**

Tras el bloque `PALETTE`/`_FALLBACK` (después de la función `color_for`), añadir:

```python
FUND_EMOJI = {
    "Agua": "💧", "Electricidad": "⚡", "Internet": "📡", "Supermercado": "🛒",
    "Arriendo/Dividendo": "🏠", "Jardín infantil": "🧒", "Auto (cuota)": "🚗",
    "Restaurantes": "🍽️", "Remesas Venezuela": "💸", "GGCC": "🏢",
    "Gasolina": "⛽", "TAG": "🛣️", "Ahorro": "🐷",
}


def emoji_for(name: str) -> str:
    return FUND_EMOJI.get(name, "•")
```

Y donde se registran los globals (junto a `templates.env.globals["color_for"] = color_for`), añadir:

```python
templates.env.globals["emoji_for"] = emoji_for
```

- [ ] **Step 2: Añadir el contexto del fondo en `_overview_ctx`**

En `dashboard/app.py`, dentro de `_overview_ctx`, antes del `return {`, añadir:

```python
    fund_rows = q.fund_status(month)
    fund_tot = q.fund_totals(month)
```

Y dentro del dict que retorna, añadir dos claves:

```python
        "fund_rows": fund_rows,
        "fund_totals": fund_tot,
```

- [ ] **Step 3: Crear `dashboard/templates/_fund.html`**

```html
{# dashboard/templates/_fund.html — Fondo Común: barra de progreso + tarjetas editables #}
<article class="fund">
  <header class="fund-header">
    <strong>Fondo Común del hogar</strong>
    <span class="fund-figures">
      <span class="muted">Pagado</span> {{ fund_totals.pagado | clp }}
      <span class="muted">/ Objetivo</span> {{ fund_totals.objetivo | clp }}
    </span>
  </header>

  <div class="fund-bar-wrap" title="Consumido vs objetivo">
    <div class="fund-bar-fill" style="width: {{ fund_totals.pct }}%"></div>
  </div>
  <p class="fund-remaining muted">Restante por pagar: <strong>{{ fund_totals.restante | clp }}</strong> ({{ fund_totals.pct }}% consumido)</p>

  <div class="fund-grid">
    {% for r in fund_rows %}
    <div class="fund-card {% if r.paid %}is-paid{% endif %}">
      <div class="fund-card-head">
        <span class="fund-emoji">{{ emoji_for(r.category) }}</span>
        <span class="fund-name">{{ r.category }}</span>
        {% if r.paid %}<span class="badge paid">Pagado</span>
        {% else %}<span class="badge pending">Pendiente</span>{% endif %}
      </div>
      <form class="fund-budget-form" hx-post="/fund/budget" hx-target="#overview"
            hx-swap="innerHTML" hx-trigger="change from:input[name='amount']">
        <input type="hidden" name="month" value="{{ month }}">
        <input type="hidden" name="category_id" value="{{ r.category_id }}">
        <label class="fund-budget-label">Presupuesto
          <span class="fund-input"><span class="peso">$</span>
            <input type="number" name="amount" min="0" step="1000"
                   value="{{ r.budget_amount | round | int }}">
          </span>
        </label>
      </form>
      <div class="fund-paid muted">Pagado: {{ r.paid_amount | clp }}</div>
    </div>
    {% endfor %}
  </div>
</article>
```

- [ ] **Step 4: Incluir el partial en `dashboard/templates/_overview.html`**

Tras el bloque del balance card (después de la línea `</article>` que cierra `balance-card`, antes del comentario `{# 3. KPIs #}`), insertar:

```html
{# 2b. Fondo Común — barra de progreso + tarjetas editables #}
{% include "_fund.html" %}
```

- [ ] **Step 5: Añadir estilos en `dashboard/static/styles.css`**

Append al final del archivo:

```css
/* ── Fondo Común ─────────────────────────────────────────── */
.fund { margin: 1rem 0; }
.fund-header { display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; flex-wrap: wrap; }
.fund-figures { font-variant-numeric: tabular-nums; }
.fund-bar-wrap { height: 14px; background: #e5e7eb; border-radius: 7px; overflow: hidden; margin: .5rem 0 .25rem; }
.fund-bar-fill { height: 100%; background: linear-gradient(90deg,#16a34a,#0891b2); transition: width .3s ease; }
.fund-remaining { margin: 0 0 .75rem; }
.fund-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: .6rem; }
.fund-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: .6rem .7rem; background: #fff; }
.fund-card.is-paid { border-color: #16a34a; background: #f0fdf4; }
.fund-card-head { display: flex; align-items: center; gap: .4rem; margin-bottom: .4rem; }
.fund-emoji { font-size: 1.1rem; }
.fund-name { font-weight: 600; font-size: .9rem; flex: 1; }
.badge { font-size: .68rem; padding: .1rem .4rem; border-radius: 999px; }
.badge.paid { background: #16a34a; color: #fff; }
.badge.pending { background: #e5e7eb; color: #374151; }
.fund-budget-label { font-size: .72rem; color: #6b7280; display: block; }
.fund-input { display: flex; align-items: center; gap: .2rem; }
.fund-input .peso { color: #6b7280; }
.fund-input input { width: 100%; padding: .2rem .3rem; font-variant-numeric: tabular-nums; }
.fund-paid { font-size: .72rem; margin-top: .3rem; }
```

- [ ] **Step 6: Reconstruir dashboard y verificar render**

Run:
```bash
make dashboard && make wait-dashboard
curl -s http://localhost:8001/ | grep -c "Fondo Común del hogar"
```
Expected: `1` (la sección renderiza). Abrir `http://localhost:8001/` muestra la barra de progreso y 13 tarjetas con emoji.

- [ ] **Step 7: Commit**

```bash
git add dashboard/app.py dashboard/templates/_fund.html dashboard/templates/_overview.html dashboard/static/styles.css
git commit -m "feat(dashboard): seccion Fondo Comun (barra de progreso + tarjetas por categoria)"
```

---

## Fase D — Dashboard: edición de presupuesto (escritura acotada)

### Task D1: Capa de escritura `writes.py` + ruta `POST /fund/budget`

**Files:**
- Create: `dashboard/writes.py`
- Modify: `dashboard/app.py`

**Interfaces:**
- Consumes: `settings.dsn` (rol `fortunia_ro` con grant INSERT/UPDATE en `fund_monthly`), `q.fund_status`/`q.fund_totals`, `_overview_ctx`.
- Produces:
  - `writes.set_budget(category_id: int, month: str, amount: int) -> None` — UPSERT de `budget_amount` por `(category_id, month)`.
  - Ruta `POST /fund/budget` (form: `category_id:int`, `month:str`, `amount:int`) → re-renderiza `_overview.html`.

- [ ] **Step 1: Crear `dashboard/writes.py`**

```python
"""Única capa de ESCRITURA del dashboard. Acotada a fund_monthly (presupuesto).

El rol fortunia_ro tiene GRANT SELECT, INSERT, UPDATE solo sobre fund_monthly
(ver db/03_ro_role.sh). Cualquier intento de escribir otra tabla falla por permisos.
"""
from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from config import settings


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.dsn, row_factory=dict_row)


def set_budget(category_id: int, month: str, amount: int) -> None:
    """Fija/actualiza el presupuesto de una categoría compartida para un mes.

    month: 'YYYY-MM'. UPSERT por (category_id, month): si la fila no existe la crea
    con paid_amount=0; si existe solo actualiza budget_amount.
    """
    month_date = f"{month}-01"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fund_monthly (category_id, month, budget_amount, paid_amount, source)
            VALUES (%(cat)s, %(month)s::date, %(amount)s, 0, 'manual')
            ON CONFLICT (category_id, month) DO UPDATE
              SET budget_amount = EXCLUDED.budget_amount,
                  updated_at    = now()
            """,
            {"cat": category_id, "month": month_date, "amount": amount},
        )
        conn.commit()
```

- [ ] **Step 2: Añadir la ruta `POST /fund/budget` en `dashboard/app.py`**

Añadir el import junto a los otros de fastapi (arriba):

```python
from fastapi import FastAPI, Form, Request
```
(añade `Form` a la línea existente `from fastapi import FastAPI, Request`).

Y junto a `import queries as q` añadir:

```python
import writes
```

Luego, después de la ruta `overview_partial`, añadir:

```python
@app.post("/fund/budget", response_class=HTMLResponse)
def fund_budget(request: Request, category_id: int = Form(...),
                month: str = Form(...), amount: int = Form(...)):
    """Edita el presupuesto mensual de una categoría compartida (escritura acotada)."""
    if amount < 0:
        amount = 0
    writes.set_budget(category_id, month, amount)
    return templates.TemplateResponse(request, "_overview.html", _overview_ctx(request, month))
```

- [ ] **Step 3: Reconstruir y probar la escritura (camino feliz)**

Run:
```bash
make dashboard && make wait-dashboard
# Tomar un category_id shared real:
CID=$(make -s psql <<'SQL'
SELECT id FROM categories WHERE name='Internet' AND classification='shared';
SQL
)
curl -s -X POST http://localhost:8001/fund/budget \
  -d "category_id=$(echo "$CID" | grep -oE '[0-9]+' | head -1)" \
  -d "month=$(date +%Y-%m)" -d "amount=33000" | grep -c "Fondo Común del hogar"
make psql <<'SQL'
SELECT category, budget_amount FROM v_fund_monthly
WHERE category='Internet' AND month = date_trunc('month', CURRENT_DATE)::date;
SQL
```
Expected: el grep devuelve `1` (re-render OK); la query muestra `budget_amount = 33000.00`.

- [ ] **Step 4: Verificar el límite de permisos (el dashboard NO puede escribir otra tabla)**

Run:
```bash
cd dashboard && python3 -c "
import writes
c = writes.connect()
try:
    with c.cursor() as cur:
        cur.execute(\"INSERT INTO incomes (amount) VALUES (1)\")
    print('FALLO: escritura permitida (no debería)')
except Exception as e:
    print('OK: bloqueado ->', type(e).__name__)
"
```
Expected: `OK: bloqueado -> InsufficientPrivilege` (el rol RO no puede escribir `incomes`).

- [ ] **Step 5: Commit**

```bash
git add dashboard/writes.py dashboard/app.py
git commit -m "feat(dashboard): edicion de presupuesto del fondo (escritura acotada a fund_monthly)"
```

---

## Fase E — E2E con Playwright

### Task E1: Scaffold Playwright + test del flujo completo

**Files:**
- Create: `e2e/requirements.txt`, `e2e/conftest.py`, `e2e/test_fondo_comun.py`
- Modify: `Makefile`

**Interfaces:**
- Consumes: dashboard en `http://localhost:8001`, worker en `http://localhost:8002` (ambos vía `make deploy`).
- Produces: target `make e2e`.

- [ ] **Step 1: Crear `e2e/requirements.txt`**

```text
pytest>=8.0
pytest-playwright>=0.5
httpx>=0.27
```

- [ ] **Step 2: Crear `e2e/conftest.py`**

```python
"""Fixtures E2E. Lee URLs de env (defaults compose) y un cliente HTTP al worker
para simular el mensaje de Telegram (openclaw -> worker /text)."""
import os

import httpx
import pytest

DASH = os.environ.get("DASHBOARD_URL", "http://localhost:8001")
WORKER = os.environ.get("WORKER_URL", "http://localhost:8002")


@pytest.fixture(scope="session")
def dashboard_url() -> str:
    return DASH


@pytest.fixture
def telegram(_skip_if_down):
    """Simula un mensaje de Telegram posteando texto libre al worker /text."""
    def _send(text: str) -> dict:
        r = httpx.post(f"{WORKER}/text", json={"text": text}, timeout=15)
        r.raise_for_status()
        return r.json()
    return _send


@pytest.fixture(scope="session")
def _skip_if_down():
    try:
        httpx.get(f"{DASH}/health", timeout=3).raise_for_status()
        httpx.get(f"{WORKER}/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("Servicios no disponibles — levanta con `make deploy`")
```

- [ ] **Step 3: Crear `e2e/test_fondo_comun.py`**

```python
"""E2E Fondo Común: declarar pago por 'Telegram' marca la categoría pagada,
baja la barra; el presupuesto es editable mes a mes; las barras de ingreso
muestran fuentes."""
import re

from playwright.sync_api import Page, expect


def _bar_width(page: Page) -> float:
    style = page.locator(".fund-bar-fill").get_attribute("style") or ""
    m = re.search(r"width:\s*([\d.]+)%", style)
    return float(m.group(1)) if m else 0.0


def test_pago_telegram_marca_pagado_y_consume_fondo(page: Page, dashboard_url, telegram, _skip_if_down):
    # Estado inicial
    page.goto(dashboard_url)
    expect(page.get_by_text("Fondo Común del hogar")).to_be_visible()
    before = _bar_width(page)

    # 'Telegram': pagar el agua
    resp = telegram("pagué 30000 de agua")
    assert resp["routed_to"] == "fund"
    assert resp["category"] == "Agua"

    # El dashboard refleja Agua pagada y la barra subió (consumo)
    page.goto(dashboard_url)
    agua_card = page.locator(".fund-card", has=page.get_by_text("Agua", exact=True))
    expect(agua_card.locator(".badge.paid")).to_be_visible()
    assert _bar_width(page) >= before


def test_idempotente_reportar_dos_veces_no_duplica(page: Page, dashboard_url, telegram, _skip_if_down):
    telegram("pagué 55000 de electricidad")
    telegram("pagué 60000 de electricidad")  # reportado de nuevo
    page.goto(dashboard_url)
    luz_card = page.locator(".fund-card", has=page.get_by_text("Electricidad", exact=True))
    expect(luz_card.get_by_text("Pagado: $60.000")).to_be_visible()  # reemplazó, no sumó


def test_editar_presupuesto_mes_a_mes(page: Page, dashboard_url, _skip_if_down):
    page.goto(dashboard_url)
    internet_card = page.locator(".fund-card", has=page.get_by_text("Internet", exact=True))
    inp = internet_card.locator("input[name='amount']")
    inp.fill("34000")
    inp.dispatch_event("change")  # dispara hx-post
    page.wait_for_timeout(800)    # espera el swap HTMX
    page.goto(dashboard_url)
    internet_card = page.locator(".fund-card", has=page.get_by_text("Internet", exact=True))
    expect(internet_card.locator("input[name='amount']")).to_have_value("34000")


def test_barras_de_ingreso_por_fuente(page: Page, dashboard_url, telegram, _skip_if_down):
    # Registrar un ingreso laboral vía worker /income (fuente = Laboral)
    import httpx, os
    httpx.post(f"{os.environ.get('WORKER_URL','http://localhost:8002')}/income",
               json={"text": "cobré 4400000 de sueldo"}, timeout=15).raise_for_status()
    page.goto(dashboard_url)
    expect(page.get_by_text("Ingresos del mes")).to_be_visible()
    expect(page.locator("#incomeChart")).to_be_visible()
```

- [ ] **Step 4: Añadir targets `test` y `e2e` al `Makefile`**

Antes de la sección `# ── help ──`, añadir:

```makefile
## test: unit + DB-integration del worker (requiere `make deploy` para los DB)
.PHONY: test
test:
	cd worker && pytest -v

## e2e: instala Playwright (si falta) y corre los tests E2E del dashboard
.PHONY: e2e
e2e:
	cd e2e && pip install -q -r requirements.txt && python -m playwright install --with-deps chromium
	cd e2e && pytest -v
```

- [ ] **Step 5: Correr la suite E2E completa**

Run:
```bash
make deploy && make fund
make e2e
```
Expected: 4 passed. (Si fallan por timing del swap HTMX, subir `wait_for_timeout`.)

- [ ] **Step 6: Commit**

```bash
git add e2e/ Makefile
git commit -m "test(e2e): Playwright Fondo Comun (pago Telegram, idempotencia, presupuesto editable, ingresos)"
```

---

## Fase F — Cierre

### Task F1: Documentación y verificación final

**Files:**
- Modify: `CLAUDE.md` (sección Data Flow / Key Files), `docs/superpowers/specs/2026-06-30-fondo-comun-design.md` (marcar implementado)

- [ ] **Step 1: Documentar el flujo del fondo en `CLAUDE.md`**

En la sección "Key Files", añadir las entradas:

```markdown
- `db/06_fund.sql` — Fondo Común: categorías compartidas, `fund_monthly`, vista `v_fund_monthly`
- `dashboard/writes.py` — única escritura del dashboard (presupuesto, acotada a `fund_monthly`)
- `dashboard/templates/_fund.html` — barra de progreso + tarjetas de categoría compartida
```

En "Common Commands" añadir bajo Database Access:

```markdown
make fund              # Aplica el DDL del Fondo Común a la DB en marcha (idempotente)
```

- [ ] **Step 2: Verificación final (todo verde)**

Run:
```bash
make deploy && make fund
make test
make e2e
make health && make health-dashboard
```
Expected: unit/DB tests passed o skipped; E2E 4 passed; ambos `/health` con `"ok": true`.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md docs/superpowers/specs/2026-06-30-fondo-comun-design.md
git commit -m "docs: documentar Fondo Comun en CLAUDE.md"
```

---

## Self-Review (cobertura del spec)

| Requisito del spec | Task |
|---|---|
| `categories.target_amount` + semillas shared + aliases | A1 |
| Tabla `fund_monthly` + vista `v_fund_monthly` | A1 |
| Grant RW acotado a `fund_monthly` | A1 (03_ro_role.sh) + D1 (verificación de límite) |
| `categorize_shared` | B1 |
| `upsert_fund_payment` idempotente por (categoría, mes) | B2 |
| `/text` ramifica a fondo, no crea receipt | B3 |
| `fund_status` / `fund_totals` | C1 |
| `_fund.html`: barra de progreso + tarjetas emoji+input (estilo hazlacorta) | C2 |
| Req #1: barras de ingreso por fuente | preexistente (`_income_bar.html`); verificado en E1 |
| Req #2: barra se vacía al declarar pagos | B3 + C2 + E1 |
| Req #3: categoría pasa a "pagado" + descuenta del fondo | B3 + C2 + E1 |
| Q2: presupuesto editable mes a mes desde la web | D1 |
| Workflow por fases (impl → unit → deploy → E2E) | A–F |

Sin placeholders. Nombres/firmas consistentes entre tasks: `categorize_shared`, `upsert_fund_payment(category_id, month, amount, source)->(paid, remaining)`, `fund_status(month)`, `fund_totals(month)`, `set_budget(category_id, month, amount)`, contexto `fund_rows`/`fund_totals`, global `emoji_for`.
```
