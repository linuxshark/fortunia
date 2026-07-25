# Presupuesto del mes siguiente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user plan next month's Fondo Común budget from the dashboard, via a 3D card-flip on the Fondo Común block that seeds and edits `fund_monthly` for `next_month(visible_month)`.

**Architecture:** Pure functions (`next_month`, `fund_delta_label`) and a read query (`fund_plan`) added to `dashboard/queries.py`; one idempotent seed write added to `dashboard/writes.py`; two routes in `dashboard/app.py` (`POST /fund/plan` new, `POST /fund/budget` extended with a `view`/`compare_to` branch); a new partial `_fund_plan.html` as the flip's back face, with `_fund.html` wrapped in a flip container; CSS for the 3D transform added to `dashboard/static/styles.css`.

**Tech Stack:** FastAPI + Jinja2 + HTMX (existing dashboard stack), psycopg3, pytest for unit tests, plus one DB-integration test following the `worker/tests/conftest.py` pattern.

## Global Constraints

- Spec source of truth: `docs/superpowers/specs/2026-07-25-presupuesto-mes-siguiente-design.md`.
- No DB schema changes — `fund_monthly` and `categories.target_amount` already cover the case.
- `seed_month_from` must be idempotent (`ON CONFLICT (category_id, month) DO NOTHING`) — never overwrite an edited amount.
- Money formatting matches the existing `clp` Jinja filter: thousands separator `.`, no decimals, prefixed `$`.
- `dashboard/writes.py` remains the *only* write surface; the RO role only has `SELECT, INSERT, UPDATE` on `fund_monthly` — every new write must go through this file and touch only that table.
- Front card (`_fund.html`'s current content/behavior, `fund_totals`, `fund_status`) must not change functionally — only wrapped in a new flip container.
- Follow existing code patterns: Spanish copy in templates/comments-with-why-only, `sys.path.insert` + module import style in `dashboard/tests/*.py` (see `test_admin.py`, `test_fund_card_state.py`).

---

## File Structure

- Modify `dashboard/queries.py` — add `next_month`, `fund_delta_label`, `fund_plan`; extend `months_available`.
- Modify `dashboard/writes.py` — add `seed_month_from`.
- Modify `dashboard/app.py` — add `POST /fund/plan`; extend `POST /fund/budget`.
- Modify `dashboard/templates/_fund.html` — wrap in `.fund-flip` container, add flip button.
- Create `dashboard/templates/_fund_plan.html` — back-face partial.
- Modify `dashboard/static/styles.css` — flip container/transform, delta colors.
- Create `dashboard/tests/conftest.py` — `db` fixture (RO dsn, matches `writes.py`'s connection), `clean_fund_plan` cleanup fixture.
- Modify `dashboard/tests/test_fund_card_state.py` — add `next_month` and `fund_delta_label` unit tests (kept in this file since it already covers pure fund-state helpers).
- Create `dashboard/tests/test_fund_plan_db.py` — DB-integration test for `seed_month_from` idempotency.

---

### Task 1: `next_month()` — pure date helper

**Files:**
- Modify: `dashboard/queries.py`
- Test: `dashboard/tests/test_fund_card_state.py`

**Interfaces:**
- Produces: `next_month(month: str) -> str`, `'YYYY-MM' -> 'YYYY-MM'`.

- [ ] **Step 1: Write the failing tests**

Add to `dashboard/tests/test_fund_card_state.py` (below the existing `fund_card_state` tests, same file — it's the home for pure fund helpers):

```python
from queries import fund_card_state, next_month  # noqa: E402


def test_next_month_mismo_anio():
    assert next_month("2026-07") == "2026-08"


def test_next_month_salto_de_anio():
    assert next_month("2026-12") == "2027-01"


def test_next_month_formato_dos_digitos():
    assert next_month("2026-01") == "2026-02"
    assert next_month("2026-09") == "2026-10"
```

Replace the existing top import line `from queries import fund_card_state  # noqa: E402` with the one above (adding `next_month` to the same import).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd dashboard && python -m pytest tests/test_fund_card_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'next_month'`

- [ ] **Step 3: Implement `next_month`**

In `dashboard/queries.py`, add near `_month_date` (around line 204):

```python
def next_month(month: str) -> str:
    """'YYYY-MM' -> mes siguiente en el mismo formato. Pura, sin DB."""
    year, mon = (int(p) for p in month.split("-"))
    if mon == 12:
        return f"{year + 1}-01"
    return f"{year}-{mon + 1:02d}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && python -m pytest tests/test_fund_card_state.py -v`
Expected: PASS, all tests including the 3 new ones.

- [ ] **Step 5: Commit**

```bash
git add dashboard/queries.py dashboard/tests/test_fund_card_state.py
git commit -m "feat(fund): add next_month() date helper"
```

---

### Task 2: `fund_delta_label()` — pure delta formatter

**Files:**
- Modify: `dashboard/queries.py`
- Test: `dashboard/tests/test_fund_card_state.py`

**Interfaces:**
- Consumes: nothing external.
- Produces: `fund_delta_label(delta: float) -> tuple[str, str]` — `(texto, css_class)`. `texto` uses `.` as thousands separator and no decimals, matching the `clp` filter's formatting (see `_clp` in `dashboard/app.py`).

- [ ] **Step 1: Write the failing tests**

Add to `dashboard/tests/test_fund_card_state.py`:

```python
from queries import fund_delta_label  # noqa: E402


def test_fund_delta_label_positivo():
    assert fund_delta_label(50000) == ("+$50.000 ▲", "is-up")


def test_fund_delta_label_negativo():
    assert fund_delta_label(-20000) == ("−$20.000 ▼", "is-down")


def test_fund_delta_label_cero():
    assert fund_delta_label(0) == ("= sin cambios", "is-same")


def test_fund_delta_label_miles_grandes():
    assert fund_delta_label(1234567) == ("+$1.234.567 ▲", "is-up")
```

(Fold this import into the same combined import line from Task 1, e.g.
`from queries import fund_card_state, fund_delta_label, next_month  # noqa: E402`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd dashboard && python -m pytest tests/test_fund_card_state.py -v`
Expected: FAIL — `ImportError: cannot import name 'fund_delta_label'`

- [ ] **Step 3: Implement `fund_delta_label`**

In `dashboard/queries.py`, add right after `next_month`:

```python
def _clp_amount(n: float) -> str:
    """Formatea un monto con separador de miles '.', sin decimales, sin signo."""
    return f"{int(round(abs(n))):,}".replace(",", ".")


def fund_delta_label(delta: float) -> tuple[str, str]:
    """Texto y clase CSS para el delta de presupuesto vs. el mes de origen."""
    if delta > 0:
        return f"+${_clp_amount(delta)} ▲", "is-up"
    if delta < 0:
        return f"−${_clp_amount(delta)} ▼", "is-down"
    return "= sin cambios", "is-same"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && python -m pytest tests/test_fund_card_state.py -v`
Expected: PASS, all tests.

- [ ] **Step 5: Commit**

```bash
git add dashboard/queries.py dashboard/tests/test_fund_card_state.py
git commit -m "feat(fund): add fund_delta_label() formatter"
```

---

### Task 3: `fund_plan()` query + `months_available()` extension

**Files:**
- Modify: `dashboard/queries.py`

**Interfaces:**
- Consumes: `connect()` (existing), `_month_date(month: str) -> str` (existing, line ~204), `fund_card_state` not needed here (no paid amounts in a future month).
- Produces: `fund_plan(month: str, compare_to: str) -> dict` returning
  `{"month": str, "rows": list[dict], "total": float}`. Each row:
  `{"category_id": int, "category": str, "budget_amount": float, "prev_budget": float, "delta": float}`.
  Also modifies `months_available() -> list[str]` (existing signature unchanged) to include months present in `fund_monthly`.

This task has no isolated unit test of its own (it hits the DB) — it's exercised end-to-end by Task 5's route test and Task 7's integration test. Implement directly, matching the existing style of `fund_status()`.

- [ ] **Step 1: Implement `fund_plan`**

In `dashboard/queries.py`, add after `fund_totals()` (which follows `fund_status()`):

```python
def fund_plan(month: str, compare_to: str) -> dict:
    """Estado de planificación de 'month' (mes futuro), comparado contra 'compare_to'.

    Misma expresión de presupuesto efectivo que fund_status() pero sin JOIN a
    v_fund_paid: un mes futuro no tiene pagos."""
    sql = """
        SELECT c.id AS category_id,
               c.name AS category,
               COALESCE(fm.budget_amount, c.target_amount, 0)::float8   AS budget_amount,
               COALESCE(fm_prev.budget_amount, c.target_amount, 0)::float8 AS prev_budget
        FROM categories c
        LEFT JOIN fund_monthly fm
          ON fm.category_id = c.id AND fm.month = %(m)s::date
        LEFT JOIN fund_monthly fm_prev
          ON fm_prev.category_id = c.id AND fm_prev.month = %(prev)s::date
        WHERE c.classification = 'shared'
        ORDER BY c.id
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": _month_date(month), "prev": _month_date(compare_to)})
        rows = cur.fetchall()
    for r in rows:
        r["delta"] = r["budget_amount"] - r["prev_budget"]
    total = sum(r["budget_amount"] for r in rows)
    return {"month": month, "rows": rows, "total": total}
```

- [ ] **Step 2: Extend `months_available`**

Replace the current `months_available()` in `dashboard/queries.py` (around line 44):

```python
def months_available() -> list[str]:
    sql = """
        SELECT DISTINCT m FROM (
            SELECT to_char(date_trunc('month', COALESCE(issued_date, created_at::date)), 'YYYY-MM') AS m
            FROM receipts WHERE deleted_at IS NULL
            UNION
            SELECT to_char(month, 'YYYY-MM') AS m
            FROM fund_monthly
        ) sub
        ORDER BY m DESC
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [r["m"] for r in cur.fetchall()]
```

- [ ] **Step 3: Manual sanity check against the running DB**

Run: `make up` (if not already running), then:
`cd dashboard && python -c "from queries import fund_plan; import json; print(json.dumps(fund_plan('2026-08', '2026-07'), default=str, indent=2))"`
Expected: prints a dict with `month`, `rows` (13 shared categories, `delta` all equal to `budget_amount` since `2026-08` has no rows yet unless already seeded), `total`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/queries.py
git commit -m "feat(fund): add fund_plan() query and include fund_monthly months in months_available()"
```

---

### Task 4: `seed_month_from()` write

**Files:**
- Modify: `dashboard/writes.py`
- Create: `dashboard/tests/conftest.py`
- Test: `dashboard/tests/test_fund_plan_db.py`

**Interfaces:**
- Consumes: `connect()` (existing in `writes.py`).
- Produces: `seed_month_from(src: str, dst: str) -> None`. Both args `'YYYY-MM'`.

- [ ] **Step 1: Create the DB fixture**

Create `dashboard/tests/conftest.py`:

```python
"""Fixtures de tests DB-integration. Conecta con el mismo dsn que usa writes.py
(rol fortunia_ro, que tiene INSERT/UPDATE solo sobre fund_monthly).

Corren contra la Postgres de compose (localhost). Precondición: `make deploy`
levantado; si no responde, se skipean.
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
def clean_fund_plan(db):
    """Borra filas de fund_monthly creadas por los tests (meses 2099-01/2099-02)."""
    yield
    with db.cursor() as cur:
        cur.execute("DELETE FROM fund_monthly WHERE month IN (DATE '2099-01-01', DATE '2099-02-01')")
```

- [ ] **Step 2: Write the failing test**

Create `dashboard/tests/test_fund_plan_db.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from writes import seed_month_from, set_budget  # noqa: E402

SRC = "2099-01"
DST = "2099-02"


def test_seed_month_from_copia_presupuestos(db, clean_fund_plan):
    set_budget(_agua_id(db), SRC, 30000)
    seed_month_from(SRC, DST)
    with db.cursor() as cur:
        cur.execute(
            "SELECT fm.budget_amount FROM fund_monthly fm "
            "JOIN categories c ON c.id = fm.category_id "
            "WHERE c.name = 'Agua' AND fm.month = DATE '2099-02-01'"
        )
        row = cur.fetchone()
        assert row is not None
        assert int(row["budget_amount"]) == 30000


def test_seed_month_from_es_idempotente_no_pisa_ediciones(db, clean_fund_plan):
    agua_id = _agua_id(db)
    set_budget(agua_id, SRC, 30000)
    seed_month_from(SRC, DST)
    set_budget(agua_id, DST, 99000)  # edición manual en el mes destino
    seed_month_from(SRC, DST)        # re-sembrar no debe pisarla

    with db.cursor() as cur:
        cur.execute(
            "SELECT budget_amount FROM fund_monthly WHERE category_id = %s AND month = DATE '2099-02-01'",
            (agua_id,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1              # sin duplicados
        assert int(rows[0]["budget_amount"]) == 99000


def _agua_id(db):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = 'Agua' AND classification = 'shared'")
        return cur.fetchone()["id"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd dashboard && python -m pytest tests/test_fund_plan_db.py -v`
Expected: FAIL — `ImportError: cannot import name 'seed_month_from'` (skip instead if DB isn't up — in that case run `make up` first from repo root).

- [ ] **Step 4: Implement `seed_month_from`**

In `dashboard/writes.py`, add after `set_budget`:

```python
def seed_month_from(src: str, dst: str) -> None:
    """Copia los presupuestos efectivos de 'src' a 'dst' para categorías compartidas.

    Idempotente (ON CONFLICT DO NOTHING): si 'dst' ya tiene filas —incluidas
    ediciones manuales— no las toca; solo crea las categorías que faltan.
    """
    src_date = f"{src}-01"
    dst_date = f"{dst}-01"
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fund_monthly (category_id, month, budget_amount, paid_amount, source)
            SELECT c.id,
                   %(dst)s::date,
                   COALESCE(fm.budget_amount, c.target_amount, 0),
                   0,
                   'manual'
            FROM categories c
            LEFT JOIN fund_monthly fm
              ON fm.category_id = c.id AND fm.month = %(src)s::date
            WHERE c.classification = 'shared'
            ON CONFLICT (category_id, month) DO NOTHING
            """,
            {"src": src_date, "dst": dst_date},
        )
        conn.commit()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd dashboard && python -m pytest tests/test_fund_plan_db.py -v`
Expected: PASS (or SKIPPED if DB unreachable — acceptable, but prefer to have `make up` running to confirm PASS at least once).

- [ ] **Step 6: Commit**

```bash
git add dashboard/writes.py dashboard/tests/conftest.py dashboard/tests/test_fund_plan_db.py
git commit -m "feat(fund): add idempotent seed_month_from() write + DB-integration tests"
```

---

### Task 5: Routes — `POST /fund/plan` and extended `POST /fund/budget`

**Files:**
- Modify: `dashboard/app.py`
- Test: `dashboard/tests/test_fund_routes.py` (new)

**Interfaces:**
- Consumes: `q.next_month`, `q.fund_plan`, `writes.seed_month_from` (Tasks 1/3/4), `writes.set_budget` (existing), `templates` (existing Jinja2Templates instance in `app.py`).
- Produces: route `POST /fund/plan` rendering `_fund_plan.html`; route `POST /fund/budget` gains optional form fields `view` and `compare_to`.

- [ ] **Step 1: Write the failing tests**

Create `dashboard/tests/test_fund_routes.py`:

```python
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402


def test_fund_plan_seeds_and_renders_back_face(monkeypatch):
    calls = {}
    monkeypatch.setattr(appmod.writes, "seed_month_from", lambda src, dst: calls.setdefault("seed", (src, dst)))
    monkeypatch.setattr(appmod.q, "fund_plan", lambda month, compare_to: {
        "month": month, "rows": [], "total": 0.0,
    })
    client = TestClient(appmod.app)
    r = client.post("/fund/plan", data={"month": "2026-07"})
    assert r.status_code == 200
    assert calls["seed"] == ("2026-07", "2026-08")


def test_fund_plan_rejects_malformed_month(monkeypatch):
    client = TestClient(appmod.app)
    r = client.post("/fund/plan", data={"month": "not-a-month"})
    assert r.status_code == 400


def test_fund_budget_view_plan_rerenders_plan_partial(monkeypatch):
    monkeypatch.setattr(appmod.writes, "set_budget", lambda *a, **k: None)
    monkeypatch.setattr(appmod.q, "fund_plan", lambda month, compare_to: {
        "month": month, "rows": [], "total": 0.0,
    })
    client = TestClient(appmod.app)
    r = client.post("/fund/budget", data={
        "category_id": "1", "month": "2026-08", "amount": "1000",
        "view": "plan", "compare_to": "2026-07",
    })
    assert r.status_code == 200


def test_fund_budget_default_view_unchanged(monkeypatch):
    monkeypatch.setattr(appmod.writes, "set_budget", lambda *a, **k: None)
    monkeypatch.setattr(appmod, "_overview_ctx", lambda request, month: {"request": request, "month": month})
    client = TestClient(appmod.app)
    r = client.post("/fund/budget", data={"category_id": "1", "month": "2026-07", "amount": "1000"})
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd dashboard && python -m pytest tests/test_fund_routes.py -v`
Expected: FAIL — `404 Not Found` for `/fund/plan` (route doesn't exist yet), and the `view=plan` test fails because `POST /fund/budget` doesn't branch on `view` yet.

- [ ] **Step 3: Implement the routes**

In `dashboard/app.py`, near the top where `queries` and `writes` are imported, confirm both are imported as `q` and `writes` (already the case per existing `fund_budget` route using `q.fund_status`/`writes.set_budget`).

Add a small validator and the new route, right before the existing `fund_budget` route (around line 133):

```python
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


@app.post("/fund/plan", response_class=HTMLResponse)
def fund_plan(request: Request, month: str = Form(...)):
    """Siembra el mes siguiente desde 'month' y renderiza la cara trasera del flip."""
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="month debe ser 'YYYY-MM'")
    target = q.next_month(month)
    writes.seed_month_from(month, target)
    plan = q.fund_plan(target, compare_to=month)
    return templates.TemplateResponse(request, "_fund_plan.html", {
        "request": request, "plan": plan, "compare_to": month,
    })
```

Modify the existing `fund_budget` route to branch on `view`:

```python
@app.post("/fund/budget", response_class=HTMLResponse)
def fund_budget(request: Request, category_id: int = Form(...),
                month: str = Form(...), amount: int = Form(...),
                view: str = Form(""), compare_to: str = Form("")):
    """Edita el presupuesto mensual de una categoría compartida (escritura acotada)."""
    if amount < 0:
        amount = 0
    writes.set_budget(category_id, month, amount)
    if view == "plan":
        plan = q.fund_plan(month, compare_to=compare_to)
        return templates.TemplateResponse(request, "_fund_plan.html", {
            "request": request, "plan": plan, "compare_to": compare_to,
        })
    return templates.TemplateResponse(request, "_overview.html", _overview_ctx(request, month))
```

In `dashboard/app.py`, the current import line (line 11) reads:
`from fastapi import FastAPI, Form, Request`
Change it to:
`from fastapi import FastAPI, Form, HTTPException, Request`

Also add `import re` to the top-level imports (it isn't currently imported) — place it with the standard-library imports, e.g. right after `from pathlib import Path` (line 8).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd dashboard && python -m pytest tests/test_fund_routes.py -v`
Expected: PASS, all 4 tests. (Note: `_fund_plan.html` doesn't exist until Task 6 — if these tests run before Task 6's template is created, they'll fail on `TemplateNotFound`. Do Task 6 first if running Task 5's tests standalone; the plan lists Task 6 next specifically so this resolves before final verification.)

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py dashboard/tests/test_fund_routes.py
git commit -m "feat(fund): add POST /fund/plan route and view=plan branch on POST /fund/budget"
```

---

### Task 6: `_fund_plan.html` back-face template

**Files:**
- Create: `dashboard/templates/_fund_plan.html`

**Interfaces:**
- Consumes: context `plan: dict` (from `q.fund_plan`, Task 3 — keys `month`, `rows`, `total`), `compare_to: str`; Jinja globals `emoji_for` (existing), filter `clp` (existing); `fund_delta_label` (Task 2) must be exposed as a Jinja global the same way `emoji_for`/`color_for` are (see `dashboard/app.py` lines ~64-66: `templates.env.globals["emoji_for"] = emoji_for`).
- Produces: renders inside `#fund-back` (the div created in Task 8).

- [ ] **Step 1: Register `fund_delta_label` as a Jinja global**

In `dashboard/app.py`, next to the existing globals registration (around line 65-66):

```python
templates.env.globals["emoji_for"] = emoji_for
templates.env.globals["fund_delta_label"] = q.fund_delta_label
```

(This line belongs to this task since the template needs it; it's a one-line addition alongside Task 5's route changes — if Task 5 already touched `app.py`, add it there too. Idempotent to state again here for a worker picking up Task 6 in isolation.)

- [ ] **Step 2: Write the template**

Create `dashboard/templates/_fund_plan.html`:

```html
{# dashboard/templates/_fund_plan.html — cara trasera del flip: presupuesto del mes siguiente #}
{% set MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] %}
{% set anio, mes_num = plan.month.split('-') %}
<article class="fund fund-plan">
  <header class="fund-header">
    <strong>Presupuesto de {{ MESES[mes_num | int] }} {{ anio }}</strong>
    <span class="fund-figures">
      <span class="muted">Objetivo</span> {{ plan.total | clp }}
    </span>
  </header>

  <button type="button" class="fund-back-btn"
          onclick="this.closest('.fund-flip').classList.remove('is-flipped')">
    ← Volver
  </button>

  <div class="fund-grid">
    {% for r in plan.rows %}
    {% set delta_text, delta_class = fund_delta_label(r.delta) %}
    <div class="fund-card fund-card-plan">
      <div class="fund-card-head">
        <span class="fund-emoji">{{ emoji_for(r.category) }}</span>
        <span class="fund-name">{{ r.category }}</span>
      </div>
      <form class="fund-budget-form" hx-post="/fund/budget" hx-target="#fund-back"
            hx-swap="innerHTML" hx-trigger="change from:input[name='amount']">
        <input type="hidden" name="month" value="{{ plan.month }}">
        <input type="hidden" name="category_id" value="{{ r.category_id }}">
        <input type="hidden" name="view" value="plan">
        <input type="hidden" name="compare_to" value="{{ compare_to }}">
        <label class="fund-budget-label">Presupuesto
          <span class="fund-input"><span class="peso">$</span>
            <input type="number" name="amount" min="0" step="1000"
                   value="{{ r.budget_amount | round | int }}">
          </span>
        </label>
      </form>
      <div class="fund-card-delta {{ delta_class }}">{{ delta_text }}</div>
    </div>
    {% endfor %}
  </div>
</article>
```

- [ ] **Step 3: Manual render check**

Run: `cd dashboard && python -c "
from fastapi.testclient import TestClient
import app as appmod
c = TestClient(appmod.app)
r = c.post('/fund/plan', data={'month': '2026-07'})
print(r.status_code)
assert 'Presupuesto de Agosto 2026' in r.text
print('OK')
"`
(Requires DB reachable — run against `make up`. If DB isn't reachable this manual check can be skipped; Task 8's browser check covers it too.)
Expected: prints `200` then `OK`.

- [ ] **Step 4: Commit**

```bash
git add dashboard/templates/_fund_plan.html dashboard/app.py
git commit -m "feat(fund): add _fund_plan.html back-face template"
```

---

### Task 7: Re-run route tests now that the template exists

**Files:**
- Test: `dashboard/tests/test_fund_routes.py` (from Task 5, no changes needed)

- [ ] **Step 1: Run the full route test file**

Run: `cd dashboard && python -m pytest tests/test_fund_routes.py -v`
Expected: PASS, all 4 tests (this confirms Task 5 + Task 6 integrate correctly now that `_fund_plan.html` exists).

- [ ] **Step 2: Run the full dashboard test suite**

Run: `cd dashboard && python -m pytest tests/ -v`
Expected: PASS (DB-integration tests SKIP if `make up` isn't running; otherwise PASS).

- [ ] **Step 3: Commit (only if any fixups were needed)**

```bash
git add dashboard/
git commit -m "test(fund): confirm fund/plan routes pass with back-face template in place"
```

(Skip this commit if Step 1/2 passed with no changes — nothing to commit.)

---

### Task 8: Flip container in `_fund.html` + flip button

**Files:**
- Modify: `dashboard/templates/_fund.html`

**Interfaces:**
- Consumes: `month` (existing context var, used for `hx-vals`), HTMX (already loaded site-wide per `base.html`).
- Produces: `.fund-flip` container wrapping the existing `<article class="fund">` as `.fund-front`, plus an empty `.fund-back` div with `id="fund-back"` as the flip target for Tasks 5/6's routes.

- [ ] **Step 1: Wrap the existing template**

Modify `dashboard/templates/_fund.html`: wrap the current `<article class="fund">...</article>` in a flip container, and add the flip button to the existing header. The full new file:

```html
{# dashboard/templates/_fund.html — Fondo Común: barra de progreso + tarjetas editables #}
<div class="fund-flip">
  <div class="fund-face fund-front">
    <article class="fund">
      <header class="fund-header">
        <strong>Fondo Común del hogar</strong>
        <span class="fund-figures">
          <span class="muted">Pagado</span> {{ fund_totals.pagado | clp }}
          <span class="muted">/ Objetivo</span> {{ fund_totals.objetivo | clp }}
        </span>
        <button type="button" class="fund-flip-btn"
                hx-post="/fund/plan" hx-target="#fund-back" hx-swap="innerHTML"
                hx-vals='{"month": "{{ month }}"}'
                hx-on::after-swap="this.closest('.fund-flip').classList.add('is-flipped')">
          Planificar mes siguiente →
        </button>
      </header>

      <div class="fund-bar-wrap" title="{{ fund_totals.pct }}% del fondo utilizado">
        <div class="fund-bar-fill" style="width: {{ fund_totals.bar_width }}%; background: {{ fund_totals.bar_color }};"></div>
      </div>
      {% if fund_totals.overspent %}
      <p class="fund-remaining fund-overspent">
        ⚠ Excedido por <strong>{{ fund_totals.excedido | clp }}</strong>
        — pagado {{ fund_totals.pagado | clp }} de {{ fund_totals.objetivo | clp }}
      </p>
      {% else %}
      <p class="fund-remaining muted">
        Fondo disponible: <strong>{{ fund_totals.restante | clp }}</strong>
        <span class="fund-pct">({{ fund_totals.pct }}% utilizado)</span>
      </p>
      {% endif %}

      <div class="fund-grid">
        {% for r in fund_rows %}
        <div class="fund-card is-{{ r.state }}">
          <div class="fund-card-head">
            <span class="fund-emoji">{{ emoji_for(r.category) }}</span>
            <span class="fund-name">{{ r.category }}</span>
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
          <div class="fund-card-bar">
            <div class="fund-card-bar-fill" style="width: {{ r.bar_width }}%;"></div>
          </div>
          <div class="fund-card-status">
            <span class="fund-card-paid">{{ r.paid_amount | clp }}</span>
            {% if r.state == 'pagado' %}<span class="badge fund-badge-paid fund-badge-icon" title="Pagado" aria-label="Pagado">✓</span>
            {% elif r.state == 'parcial' %}<span class="badge fund-badge-partial">Parcial</span>
            {% elif r.state == 'excedido' %}<span class="badge fund-badge-over fund-badge-icon" title="Excedido" aria-label="Excedido">⚠</span>
            {% else %}<span class="badge fund-badge-pending">Pendiente</span>{% endif %}
          </div>
        </div>
        {% endfor %}
      </div>
    </article>
  </div>
  <div class="fund-face fund-back" id="fund-back"></div>
</div>
```

Note: only two changes from the original file — the `.fund-flip`/`.fund-face` wrapper divs, and the new `<button class="fund-flip-btn">` inside `.fund-header`. Everything else is byte-identical to the pre-existing template.

- [ ] **Step 2: Commit**

```bash
git add dashboard/templates/_fund.html
git commit -m "feat(fund): wrap Fondo Común in flip container with 'Planificar mes siguiente' button"
```

---

### Task 9: CSS for the 3D flip and delta colors

**Files:**
- Modify: `dashboard/static/styles.css`

**Interfaces:**
- Consumes: existing CSS variables `--accent`, `--warn`, `--danger`, `--muted`, `--border`, `--bg-surface`, `--radius`, `--font-mono` (all defined in the `:root` block, lines ~15-21).
- Produces: `.fund-flip`, `.fund-face`, `.fund-front`, `.fund-back`, `.is-flipped`, `.fund-flip-btn`, `.fund-back-btn`, `.fund-card-plan`, `.fund-card-delta.is-up/.is-down/.is-same`.

- [ ] **Step 1: Add the CSS**

In `dashboard/static/styles.css`, add right after the existing Fondo Común block (after the last `.fund-*` rule, which ends around line 280+ — append at the end of that section, before the next `/* ── ... ── */` section header):

```css
/* ── Fondo Común: flip al presupuesto del mes siguiente ─────── */
.fund-flip {
  display: grid;
  transform-style: preserve-3d;
  transition: transform .45s ease;
}
.fund-flip.is-flipped { transform: rotateY(180deg); }
.fund-face {
  grid-area: 1 / 1;
  backface-visibility: hidden;
  min-width: 0;
}
.fund-front { perspective: 1600px; }
.fund-back { transform: rotateY(180deg); }
.fund-back:empty { visibility: hidden; }

.fund-flip-btn, .fund-back-btn {
  font-family: var(--font-mono); font-size: .68rem;
  letter-spacing: .03em; color: var(--accent);
  background: var(--accent-dim); border: 1px solid rgba(52,211,153,.3);
  border-radius: 6px; padding: .25rem .55rem; cursor: pointer;
  transition: background .15s, border-color .15s;
}
.fund-flip-btn:hover, .fund-back-btn:hover { border-color: var(--accent); }
.fund-back-btn { margin-bottom: .6rem; }

.fund-card-plan { border-color: var(--border); }
.fund-card-delta {
  margin-top: .5rem; font-family: var(--font-mono); font-size: .68rem;
  font-variant-numeric: tabular-nums;
}
.fund-card-delta.is-up   { color: var(--warn); }
.fund-card-delta.is-down { color: var(--accent); }
.fund-card-delta.is-same { color: var(--muted); }

@media (prefers-reduced-motion: reduce) {
  .fund-flip { transition: none; }
  .fund-flip.is-flipped { transform: none; }
  .fund-front, .fund-back { transition: opacity .15s ease; }
  .fund-flip:not(.is-flipped) .fund-back { opacity: 0; pointer-events: none; }
  .fund-flip.is-flipped .fund-front { opacity: 0; pointer-events: none; }
  .fund-flip.is-flipped .fund-back { transform: none; opacity: 1; }
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/static/styles.css
git commit -m "style(fund): add 3D flip transform and delta colors for the plan back-face"
```

---

### Task 10: End-to-end browser verification

**Files:** none (verification only)

- [ ] **Step 1: Start the stack**

Run: `make up` (or `make deploy` if not yet built) from the repo root.

- [ ] **Step 2: Open the dashboard and exercise the flip**

Use the `run` skill or a browser to open `http://localhost:8001/` (or the configured `DASHBOARD_PORT`). Confirm:
- The Fondo Común block renders unchanged (front face).
- Clicking "Planificar mes siguiente →" flips the card in ~450ms and shows next month's categories with the current budgets pre-filled and `= sin cambios` deltas (first time — nothing seeded yet).
- Editing one amount updates that card's delta immediately (e.g. raising Agua by $10.000 shows `+$10.000 ▲` in warn/orange) and updates the header total, without a full page flip-back.
- Clicking "← Volver" returns to the front face without a network request (check via devtools network tab — no request fires).
- Reload the page, click flip again: previously-edited amount persists (seed didn't overwrite it) — confirms `ON CONFLICT DO NOTHING` idempotency end-to-end.
- The month selector on the page now includes the newly-planned month.

- [ ] **Step 3: Report results**

If any check fails, note which one and fix before proceeding — do not mark this task done on partial success.

---

## Self-Review Notes

- **Spec coverage:** Problem/Solution → Tasks 1,3,4,8. `next_month` → Task 1. `fund_plan`/`fund_delta_label` → Tasks 2,3. `seed_month_from` idempotency → Task 4. `months_available` union → Task 3. Routes (`/fund/plan`, extended `/fund/budget`) → Task 5. Templates (`_fund.html` flip wrapper, `_fund_plan.html`) → Tasks 6,8. CSS/flip mechanics/reduced-motion → Task 9. Error handling (month validation, negative amount clamp, `after-swap` gating) → Tasks 5,8. Testing section (unit + DB-integration) → Tasks 1,2,4. E2E confirmation → Task 10.
- **Placeholder scan:** no TBD/TODO; all steps carry literal code.
- **Type consistency:** `fund_plan(month, compare_to)` signature matches every call site (Task 3 def, Task 5 both routes, Task 6 template usage via Jinja global). `next_month(month: str) -> str` consistent between Task 1 and Task 5's usage. `fund_delta_label(delta: float) -> tuple[str, str]` consistent between Task 2's def and Task 6's template unpacking (`{% set delta_text, delta_class = fund_delta_label(r.delta) %}`).
