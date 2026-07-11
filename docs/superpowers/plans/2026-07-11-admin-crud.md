# Admin CRUD de Transacciones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Fortunia administrator a way to list, edit, and (soft-)delete every transaction (receipts/line_items, incomes, fund_payments) through new `/admin/*` endpoints in the worker service, and ship a Postman collection to drive them.

**Architecture:** New endpoints live in the **worker** (`:8002`), not the dashboard, because the worker already holds the DB owner role (dashboard is deliberately read-only). A new `worker/admin_db.py` module holds raw SQL CRUD helpers (list/update/soft-delete/restore) reusing `db.connect()`. A new `worker/admin.py` module defines the FastAPI `APIRouter` (Pydantic models + HTTP wiring) and is mounted onto the existing `app` in `worker/app.py`. `deleted_at` soft-delete columns are added to `fund_payments` and `line_items` (receipts/incomes already have them); analytical views and dashboard queries are updated to exclude soft-deleted rows so a deleted transaction stops counting everywhere it matters. No new authentication — matches every other endpoint in this local-only app.

**Tech Stack:** FastAPI, Pydantic, psycopg3 (dict rows), PostgreSQL 16, pytest (DB-integration style, real Postgres via `make deploy`), Postman collection format v2.1.

## Global Constraints

- Money stays `NUMERIC`, never float — psycopg returns `Decimal` for `NUMERIC` columns; assert with `float(...)` in tests, never assume plain float equality issues.
- All new SQL migrations must be idempotent (`ADD COLUMN IF NOT EXISTS`, `CREATE OR REPLACE VIEW` / `DROP VIEW IF EXISTS` + `CREATE VIEW`) — same pattern as `db/06_fund.sql`/`db/07_fund_payments.sql`.
- No authentication on `/admin/*` — this is an explicit, documented decision (see spec), not a gap to fill.
- Soft-delete only: `DELETE` endpoints set `deleted_at = now()`, never `DELETE FROM`.
- `PATCH` payloads only accept the exact fields listed per entity in the spec — no generic "update any column" endpoint.
- Tests are DB-integration style (real Postgres via the `db` pytest fixture in `worker/tests/conftest.py`), not mocked — follow the existing pattern in `worker/tests/test_fund_db.py`.

---

## Task 1: Schema migration — soft-delete columns + view updates

**Files:**
- Create: `db/09_admin_soft_delete.sql`
- Modify: `db/07_fund_payments.sql` (view definition only)
- Modify: `docker-compose.yml:43` (add volume mount after line 43)
- Modify: `Makefile:241-250` (`fund` target)

**Interfaces:**
- Produces: `fund_payments.deleted_at`, `line_items.deleted_at` columns (both `TIMESTAMPTZ`, nullable). `v_fund_paid` excludes rows where `fund_payments.deleted_at IS NOT NULL`. Later tasks (`admin_db.py`, `dashboard/queries.py`) rely on these columns existing.

- [ ] **Step 1: Write the migration file**

Create `db/09_admin_soft_delete.sql`:

```sql
-- db/09_admin_soft_delete.sql — Soft-delete para el panel admin. Idempotente.
--
-- receipts e incomes ya tienen deleted_at. fund_payments y line_items no lo
-- tenían porque nada los borraba hasta ahora. El panel admin (worker /admin/*)
-- necesita poder "deshacer" un borrado, así que se usa soft-delete en todo:
-- ver docs/superpowers/specs/2026-07-11-admin-crud-design.md.

ALTER TABLE fund_payments ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE line_items    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_fund_payments_deleted ON fund_payments (deleted_at);
CREATE INDEX IF NOT EXISTS idx_line_items_deleted ON line_items (deleted_at);
```

- [ ] **Step 2: Update `v_fund_paid` to exclude soft-deleted payments**

In `db/07_fund_payments.sql`, find the `v_fund_paid` view definition:

```sql
CREATE OR REPLACE VIEW v_fund_paid AS
SELECT fp.category_id, fp.month,
       CASE WHEN c.accumulation_mode = 'sum'
            THEN SUM(fp.amount)
            ELSE (array_agg(fp.amount ORDER BY fp.paid_at DESC, fp.id DESC))[1]
       END                    AS paid_amount,
       MAX(fp.paid_at)        AS paid_at
FROM fund_payments fp
JOIN categories c ON c.id = fp.category_id
GROUP BY fp.category_id, fp.month, c.accumulation_mode;
```

Replace with (adds a `WHERE` clause):

```sql
CREATE OR REPLACE VIEW v_fund_paid AS
SELECT fp.category_id, fp.month,
       CASE WHEN c.accumulation_mode = 'sum'
            THEN SUM(fp.amount)
            ELSE (array_agg(fp.amount ORDER BY fp.paid_at DESC, fp.id DESC))[1]
       END                    AS paid_amount,
       MAX(fp.paid_at)        AS paid_at
FROM fund_payments fp
JOIN categories c ON c.id = fp.category_id
WHERE fp.deleted_at IS NULL
GROUP BY fp.category_id, fp.month, c.accumulation_mode;
```

This view is created with `CREATE OR REPLACE`, so re-running `06/07/08_*.sql` picks up the change without a `DROP VIEW`. `v_fund_monthly` (further down in the same file) already reads through `v_fund_paid` via a `LEFT JOIN`, so it needs no direct change — a soft-deleted payment simply stops appearing there too.

- [ ] **Step 3: Mount the new migration file in compose**

In `docker-compose.yml`, after line 43 (`./db/08_ocr_fund.sql:/docker-entrypoint-initdb.d/08_ocr_fund.sql:ro`), add:

```yaml
      - ./db/09_admin_soft_delete.sql:/docker-entrypoint-initdb.d/09_admin_soft_delete.sql:ro
```

- [ ] **Step 4: Wire the new file into `make fund`**

In `Makefile`, update the `fund` target's comment and body:

```makefile
## fund: aplica el DDL del fondo (06_fund.sql..09_admin_soft_delete.sql) a la DB en marcha (idempotente)
.PHONY: fund
fund:
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/06_fund.sql
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/07_fund_payments.sql
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/08_ocr_fund.sql
	$(COMPOSE) exec -T postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} < db/09_admin_soft_delete.sql
	@$(MAKE) --no-print-directory ro-role
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-boleta} -d $${POSTGRES_DB:-boletas} \
		-c "GRANT SELECT, INSERT, UPDATE ON fund_monthly TO $${POSTGRES_RO_USER:-fortunia_ro};"
	@echo "✓ Fondo Común aplicado (schema + grant RW acotado)"
```

- [ ] **Step 5: Apply and verify against the running DB**

Run: `make fund`
Expected: output ends with `✓ Fondo Común aplicado (schema + grant RW acotado)`, no errors.

Run:
```bash
docker compose exec -T postgres psql -U boleta -d boletas -c "\d fund_payments" | grep deleted_at
docker compose exec -T postgres psql -U boleta -d boletas -c "\d line_items" | grep deleted_at
```
Expected: both show a `deleted_at | timestamp with time zone` line.

- [ ] **Step 6: Commit**

```bash
git add db/09_admin_soft_delete.sql db/07_fund_payments.sql docker-compose.yml Makefile
git commit -m "feat(db): soft-delete columns on fund_payments/line_items + view filter"
```

---

## Task 2: `worker/admin_db.py` — receipts & line_items CRUD helpers

**Files:**
- Create: `worker/admin_db.py`
- Modify: `worker/tests/conftest.py` (add fixtures)
- Create: `worker/tests/test_admin_db.py`

**Interfaces:**
- Consumes: `db.connect()` from `worker/db.py:18` (returns `psycopg.Connection` with `dict_row` factory).
- Produces (used by Task 3 and Task 4): `list_receipts(month: str | None) -> list[dict]`, `list_receipt_items(receipt_id: int) -> list[dict]`, `update_receipt(receipt_id: int, total: float | None, issued_date) -> dict | None`, `soft_delete_receipt(receipt_id: int) -> dict | None`, `restore_receipt(receipt_id: int) -> dict | None`, `update_line_item(item_id: int, unit_price, qty, line_total, category_id) -> dict | None`, `soft_delete_line_item(item_id: int) -> dict | None`, `restore_line_item(item_id: int) -> dict | None`. Also module-private helpers `_fetchall`, `_fetchone_write`, `_fetchone_read`, `_month_date` reused by Task 3.

- [ ] **Step 1: Add shared test fixtures to `worker/tests/conftest.py`**

Append to `worker/tests/conftest.py`:

```python
from datetime import date

ADMIN_TEST_MONTH = date(2099, 2, 1)


@pytest.fixture
def shared_category_id(db):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name='Agua' AND classification='shared'")
        return cur.fetchone()[0]


@pytest.fixture
def admin_receipt(db):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO receipts (doc_type, issued_date, total, header_source, validation_status) "
            "VALUES ('texto', %s, 1000, 'texto', 'ok') RETURNING id",
            (ADMIN_TEST_MONTH,),
        )
        rid = cur.fetchone()[0]
    yield rid
    with db.cursor() as cur:
        cur.execute("DELETE FROM receipts WHERE id = %s", (rid,))


@pytest.fixture
def admin_line_item(db, admin_receipt):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO line_items (receipt_id, line_no, raw_text, qty, unit_price, line_total) "
            "VALUES (%s, 1, 'test item', 1, 1000, 1000) RETURNING id",
            (admin_receipt,),
        )
        lid = cur.fetchone()[0]
    yield lid
    with db.cursor() as cur:
        cur.execute("DELETE FROM line_items WHERE id = %s", (lid,))


@pytest.fixture
def admin_income(db):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO incomes (amount, source_text, raw_text, issued_date) "
            "VALUES (500000, 'test', 'test income', %s) RETURNING id",
            (ADMIN_TEST_MONTH,),
        )
        iid = cur.fetchone()[0]
    yield iid
    with db.cursor() as cur:
        cur.execute("DELETE FROM incomes WHERE id = %s", (iid,))


@pytest.fixture
def admin_fund_payment(db, shared_category_id):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO fund_payments (category_id, month, amount, detail, source) "
            "VALUES (%s, %s, 30000, 'test', 'telegram') RETURNING id",
            (shared_category_id, ADMIN_TEST_MONTH),
        )
        pid = cur.fetchone()[0]
    yield pid
    with db.cursor() as cur:
        cur.execute("DELETE FROM fund_payments WHERE id = %s", (pid,))
```

Note: `db` fixture in this file has `conn.autocommit = True` (see existing fixture at the top of `conftest.py`), so these raw inserts/deletes commit immediately without an explicit `conn.commit()`.

- [ ] **Step 2: Write the failing tests for receipts + line_items**

Create `worker/tests/test_admin_db.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_db  # noqa: E402


def test_list_receipts_filters_by_month(admin_receipt):
    rows = admin_db.list_receipts("2099-02")
    assert any(r["id"] == admin_receipt for r in rows)


def test_list_receipts_month_no_match(admin_receipt):
    rows = admin_db.list_receipts("2099-01")
    assert all(r["id"] != admin_receipt for r in rows)


def test_list_receipts_no_month_includes_all(admin_receipt):
    rows = admin_db.list_receipts(None)
    assert any(r["id"] == admin_receipt for r in rows)


def test_update_receipt_total(admin_receipt):
    row = admin_db.update_receipt(admin_receipt, total=2500, issued_date=None)
    assert float(row["total"]) == 2500


def test_update_receipt_not_found():
    assert admin_db.update_receipt(999999999, total=1, issued_date=None) is None


def test_soft_delete_and_restore_receipt(admin_receipt):
    deleted = admin_db.soft_delete_receipt(admin_receipt)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_receipt(admin_receipt)
    assert restored["deleted_at"] is None


def test_deleted_receipt_disappears_and_restored_reappears_in_list(admin_receipt):
    admin_db.soft_delete_receipt(admin_receipt)
    rows = admin_db.list_receipts("2099-02")
    assert all(r["id"] != admin_receipt for r in rows)
    admin_db.restore_receipt(admin_receipt)
    rows = admin_db.list_receipts("2099-02")
    assert any(r["id"] == admin_receipt for r in rows)


def test_list_receipt_items(admin_line_item, admin_receipt):
    rows = admin_db.list_receipt_items(admin_receipt)
    assert any(r["id"] == admin_line_item for r in rows)


def test_update_line_item_category(admin_line_item, shared_category_id):
    row = admin_db.update_line_item(
        admin_line_item, unit_price=None, qty=None, line_total=None, category_id=shared_category_id
    )
    assert row["category_id"] == shared_category_id


def test_update_line_item_amount(admin_line_item):
    row = admin_db.update_line_item(
        admin_line_item, unit_price=2000, qty=None, line_total=2000, category_id=None
    )
    assert float(row["line_total"]) == 2000


def test_soft_delete_and_restore_line_item(admin_line_item):
    deleted = admin_db.soft_delete_line_item(admin_line_item)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_line_item(admin_line_item)
    assert restored["deleted_at"] is None


def test_deleted_line_item_disappears_and_restored_reappears_in_list(admin_line_item, admin_receipt):
    admin_db.soft_delete_line_item(admin_line_item)
    rows = admin_db.list_receipt_items(admin_receipt)
    assert all(r["id"] != admin_line_item for r in rows)
    admin_db.restore_line_item(admin_line_item)
    rows = admin_db.list_receipt_items(admin_receipt)
    assert any(r["id"] == admin_line_item for r in rows)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd worker && python3 -m pytest tests/test_admin_db.py -v`
Expected: `ModuleNotFoundError: No module named 'admin_db'` (module doesn't exist yet).

- [ ] **Step 4: Implement `worker/admin_db.py` (receipts + line_items)**

Create `worker/admin_db.py`:

```python
"""Admin CRUD helpers: list/edit/soft-delete/restore para correcciones manuales.

A diferencia de db.py (ingesta desde OCR/Telegram, solo INSERT), este módulo
sirve al panel admin (worker/admin.py + colección Postman): permite corregir
o borrar filas ya persistidas. Reusa db.connect() — el worker ya tiene el rol
dueño de la DB, a diferencia del dashboard (solo lectura).
See docs/superpowers/specs/2026-07-11-admin-crud-design.md.
"""
from __future__ import annotations

import db


def _fetchall(sql: str, params: dict) -> list[dict]:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _fetchone_write(sql: str, params: dict) -> dict | None:
    """Para UPDATE ... RETURNING *: ejecuta, hace commit, devuelve la fila o None."""
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        conn.commit()
        return row


def _fetchone_read(sql: str, params: dict) -> dict | None:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _month_date(month: str) -> str:
    """'YYYY-MM' -> 'YYYY-MM-01' (primer día, formato de fund_payments.month)."""
    return f"{month}-01"


def list_receipts(month: str | None) -> list[dict]:
    where = ["r.deleted_at IS NULL"]
    params: dict = {}
    if month:
        where.append("to_char(r.issued_date, 'YYYY-MM') = %(m)s")
        params["m"] = month
    sql = f"""
        SELECT r.id, r.issued_date, r.total, r.doc_type, r.validation_status,
               r.fund_category_id, r.deleted_at,
               COALESCE(mc.name, 'Sin comercio') AS merchant
        FROM receipts r
        LEFT JOIN merchants mc ON mc.id = r.merchant_id
        WHERE {' AND '.join(where)}
        ORDER BY r.issued_date DESC NULLS LAST, r.id DESC
    """
    return _fetchall(sql, params)


def list_receipt_items(receipt_id: int) -> list[dict]:
    sql = """
        SELECT li.id, li.line_no, li.raw_text, li.normalized_name, li.category_id,
               li.qty, li.unit_price, li.line_total, li.deleted_at
        FROM line_items li
        WHERE li.receipt_id = %(id)s AND li.deleted_at IS NULL
        ORDER BY li.line_no
    """
    return _fetchall(sql, {"id": receipt_id})


def update_receipt(receipt_id: int, total: float | None, issued_date) -> dict | None:
    fields: dict = {}
    if total is not None:
        fields["total"] = total
    if issued_date is not None:
        fields["issued_date"] = issued_date
    if not fields:
        return _fetchone_read("SELECT * FROM receipts WHERE id = %(id)s", {"id": receipt_id})
    set_clause = ", ".join(f"{col} = %({col})s" for col in fields)
    fields["id"] = receipt_id
    return _fetchone_write(f"UPDATE receipts SET {set_clause} WHERE id = %(id)s RETURNING *", fields)


def soft_delete_receipt(receipt_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE receipts SET deleted_at = now() WHERE id = %(id)s RETURNING *", {"id": receipt_id}
    )


def restore_receipt(receipt_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE receipts SET deleted_at = NULL WHERE id = %(id)s RETURNING *", {"id": receipt_id}
    )


def update_line_item(
    item_id: int, unit_price: float | None, qty: float | None,
    line_total: float | None, category_id: int | None,
) -> dict | None:
    fields: dict = {}
    if unit_price is not None:
        fields["unit_price"] = unit_price
    if qty is not None:
        fields["qty"] = qty
    if line_total is not None:
        fields["line_total"] = line_total
    if category_id is not None:
        fields["category_id"] = category_id
    if not fields:
        return _fetchone_read("SELECT * FROM line_items WHERE id = %(id)s", {"id": item_id})
    set_clause = ", ".join(f"{col} = %({col})s" for col in fields)
    fields["id"] = item_id
    return _fetchone_write(f"UPDATE line_items SET {set_clause} WHERE id = %(id)s RETURNING *", fields)


def soft_delete_line_item(item_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE line_items SET deleted_at = now() WHERE id = %(id)s RETURNING *", {"id": item_id}
    )


def restore_line_item(item_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE line_items SET deleted_at = NULL WHERE id = %(id)s RETURNING *", {"id": item_id}
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd worker && python3 -m pytest tests/test_admin_db.py -v`
Expected: all `PASS` (12 tests). Precondition: `make deploy` / `make fund` from Task 1 already applied to the running DB (the `db` fixture skips with a message otherwise).

- [ ] **Step 6: Commit**

```bash
git add worker/admin_db.py worker/tests/conftest.py worker/tests/test_admin_db.py
git commit -m "feat(worker): admin CRUD helpers for receipts and line_items"
```

---

## Task 3: `worker/admin_db.py` — incomes, fund_payments & categories

**Files:**
- Modify: `worker/admin_db.py` (append functions)
- Modify: `worker/tests/test_admin_db.py` (append tests)

**Interfaces:**
- Consumes: `_fetchall`, `_fetchone_write`, `_fetchone_read`, `_month_date` from Task 2 (same file).
- Produces (used by Task 4): `list_incomes(month: str | None) -> list[dict]`, `update_income(income_id, amount, category_id, issued_date, raw_text) -> dict | None`, `soft_delete_income(income_id) -> dict | None`, `restore_income(income_id) -> dict | None`, `list_fund_payments(month: str | None) -> list[dict]`, `update_fund_payment(payment_id, amount, category_id, month, detail) -> dict | None`, `soft_delete_fund_payment(payment_id) -> dict | None`, `restore_fund_payment(payment_id) -> dict | None`, `list_categories() -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

Append to `worker/tests/test_admin_db.py`:

```python
def test_list_incomes_filters_by_month(admin_income):
    rows = admin_db.list_incomes("2099-02")
    assert any(r["id"] == admin_income for r in rows)


def test_update_income_amount(admin_income):
    row = admin_db.update_income(
        admin_income, amount=600000, category_id=None, issued_date=None, raw_text=None
    )
    assert float(row["amount"]) == 600000


def test_update_income_not_found():
    assert admin_db.update_income(999999999, amount=1, category_id=None, issued_date=None, raw_text=None) is None


def test_soft_delete_and_restore_income(admin_income):
    deleted = admin_db.soft_delete_income(admin_income)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_income(admin_income)
    assert restored["deleted_at"] is None


def test_deleted_income_disappears_and_restored_reappears_in_list(admin_income):
    admin_db.soft_delete_income(admin_income)
    rows = admin_db.list_incomes("2099-02")
    assert all(r["id"] != admin_income for r in rows)
    admin_db.restore_income(admin_income)
    rows = admin_db.list_incomes("2099-02")
    assert any(r["id"] == admin_income for r in rows)


def test_list_fund_payments_filters_by_month(admin_fund_payment):
    rows = admin_db.list_fund_payments("2099-02")
    assert any(r["id"] == admin_fund_payment for r in rows)


def test_update_fund_payment_amount(admin_fund_payment):
    row = admin_db.update_fund_payment(
        admin_fund_payment, amount=40000, category_id=None, month=None, detail=None
    )
    assert float(row["amount"]) == 40000


def test_soft_delete_and_restore_fund_payment(admin_fund_payment):
    deleted = admin_db.soft_delete_fund_payment(admin_fund_payment)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_fund_payment(admin_fund_payment)
    assert restored["deleted_at"] is None


def test_deleted_fund_payment_disappears_and_restored_reappears_in_list(admin_fund_payment):
    admin_db.soft_delete_fund_payment(admin_fund_payment)
    rows = admin_db.list_fund_payments("2099-02")
    assert all(r["id"] != admin_fund_payment for r in rows)
    admin_db.restore_fund_payment(admin_fund_payment)
    rows = admin_db.list_fund_payments("2099-02")
    assert any(r["id"] == admin_fund_payment for r in rows)


def test_soft_deleted_fund_payment_excluded_from_v_fund_paid(db, admin_fund_payment, shared_category_id):
    from datetime import date
    admin_db.soft_delete_fund_payment(admin_fund_payment)
    with db.cursor() as cur:
        cur.execute(
            "SELECT paid_amount FROM v_fund_paid WHERE category_id=%s AND month=%s",
            (shared_category_id, date(2099, 2, 1)),
        )
        row = cur.fetchone()
    assert row is None


def test_list_categories_nonempty():
    assert len(admin_db.list_categories()) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && python3 -m pytest tests/test_admin_db.py -v -k "income or fund_payment or categories"`
Expected: `AttributeError: module 'admin_db' has no attribute 'list_incomes'` (and similar for the others).

- [ ] **Step 3: Append the implementation to `worker/admin_db.py`**

Append to `worker/admin_db.py`:

```python
def list_incomes(month: str | None) -> list[dict]:
    where = ["i.deleted_at IS NULL"]
    params: dict = {}
    if month:
        where.append("to_char(i.issued_date, 'YYYY-MM') = %(m)s")
        params["m"] = month
    sql = f"""
        SELECT i.id, i.issued_date, i.amount, i.category_id, i.source_text,
               i.raw_text, i.deleted_at,
               COALESCE(c.name, 'Sin categoría') AS category
        FROM incomes i
        LEFT JOIN categories c ON c.id = i.category_id
        WHERE {' AND '.join(where)}
        ORDER BY i.issued_date DESC, i.id DESC
    """
    return _fetchall(sql, params)


def update_income(
    income_id: int, amount: float | None, category_id: int | None,
    issued_date, raw_text: str | None,
) -> dict | None:
    fields: dict = {}
    if amount is not None:
        fields["amount"] = amount
    if category_id is not None:
        fields["category_id"] = category_id
    if issued_date is not None:
        fields["issued_date"] = issued_date
    if raw_text is not None:
        fields["raw_text"] = raw_text
    if not fields:
        return _fetchone_read("SELECT * FROM incomes WHERE id = %(id)s", {"id": income_id})
    set_clause = ", ".join(f"{col} = %({col})s" for col in fields)
    fields["id"] = income_id
    return _fetchone_write(f"UPDATE incomes SET {set_clause} WHERE id = %(id)s RETURNING *", fields)


def soft_delete_income(income_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE incomes SET deleted_at = now() WHERE id = %(id)s RETURNING *", {"id": income_id}
    )


def restore_income(income_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE incomes SET deleted_at = NULL WHERE id = %(id)s RETURNING *", {"id": income_id}
    )


def list_fund_payments(month: str | None) -> list[dict]:
    where = ["fp.deleted_at IS NULL"]
    params: dict = {}
    if month:
        where.append("fp.month = %(m)s::date")
        params["m"] = _month_date(month)
    sql = f"""
        SELECT fp.id, fp.month, fp.amount, fp.category_id, fp.detail, fp.source,
               fp.paid_at, fp.receipt_id, fp.deleted_at,
               c.name AS category
        FROM fund_payments fp
        JOIN categories c ON c.id = fp.category_id
        WHERE {' AND '.join(where)}
        ORDER BY fp.paid_at DESC, fp.id DESC
    """
    return _fetchall(sql, params)


def update_fund_payment(
    payment_id: int, amount: float | None, category_id: int | None,
    month, detail: str | None,
) -> dict | None:
    fields: dict = {}
    if amount is not None:
        fields["amount"] = amount
    if category_id is not None:
        fields["category_id"] = category_id
    if month is not None:
        fields["month"] = month
    if detail is not None:
        fields["detail"] = detail
    if not fields:
        return _fetchone_read("SELECT * FROM fund_payments WHERE id = %(id)s", {"id": payment_id})
    set_clause = ", ".join(f"{col} = %({col})s" for col in fields)
    fields["id"] = payment_id
    return _fetchone_write(f"UPDATE fund_payments SET {set_clause} WHERE id = %(id)s RETURNING *", fields)


def soft_delete_fund_payment(payment_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE fund_payments SET deleted_at = now() WHERE id = %(id)s RETURNING *", {"id": payment_id}
    )


def restore_fund_payment(payment_id: int) -> dict | None:
    return _fetchone_write(
        "UPDATE fund_payments SET deleted_at = NULL WHERE id = %(id)s RETURNING *", {"id": payment_id}
    )


def list_categories() -> list[dict]:
    sql = "SELECT id, name, classification FROM categories ORDER BY classification, name"
    return _fetchall(sql, {})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd worker && python3 -m pytest tests/test_admin_db.py -v`
Expected: all `PASS` (23 tests total: 12 from Task 2 + 11 here).

- [ ] **Step 5: Commit**

```bash
git add worker/admin_db.py worker/tests/test_admin_db.py
git commit -m "feat(worker): admin CRUD helpers for incomes, fund_payments and categories"
```

---

## Task 4: `worker/admin.py` router + wire into `worker/app.py`

**Files:**
- Create: `worker/admin.py`
- Modify: `worker/app.py:1-22` (imports + router mount)
- Create: `worker/tests/test_admin_api.py`

**Interfaces:**
- Consumes: every function from `worker/admin_db.py` (Tasks 2-3).
- Produces: `router` (FastAPI `APIRouter`, prefix `/admin`) importable as `from admin import router as admin_router`. Mounted onto `app` in `worker/app.py`. This is the last task that touches the worker — later tasks (Postman) only depend on the HTTP contract, not Python internals.

- [ ] **Step 1: Write the failing API tests**

Create `worker/tests/test_admin_api.py`:

```python
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_list_categories_endpoint(client, db):
    resp = client.get("/admin/categories")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_patch_income_not_found(client, db):
    resp = client.patch("/admin/incomes/999999999", json={"amount": 100})
    assert resp.status_code == 404


def test_income_crud_roundtrip(client, db, admin_income):
    resp = client.get("/admin/incomes", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_income for row in resp.json())

    resp = client.patch(f"/admin/incomes/{admin_income}", json={"amount": 700000})
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 700000

    resp = client.delete(f"/admin/incomes/{admin_income}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None

    resp = client.post(f"/admin/incomes/{admin_income}/restore")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is None


def test_receipt_and_line_item_crud_roundtrip(client, db, admin_receipt, admin_line_item):
    resp = client.get("/admin/receipts", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_receipt for row in resp.json())

    resp = client.get(f"/admin/receipts/{admin_receipt}/items")
    assert resp.status_code == 200
    assert any(row["id"] == admin_line_item for row in resp.json())

    resp = client.patch(f"/admin/line-items/{admin_line_item}", json={"line_total": 5000})
    assert resp.status_code == 200
    assert float(resp.json()["line_total"]) == 5000

    resp = client.delete(f"/admin/receipts/{admin_receipt}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None

    resp = client.post(f"/admin/receipts/{admin_receipt}/restore")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is None


def test_fund_payment_crud_roundtrip(client, db, admin_fund_payment):
    resp = client.get("/admin/fund-payments", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_fund_payment for row in resp.json())

    resp = client.patch(f"/admin/fund-payments/{admin_fund_payment}", json={"amount": 45000})
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 45000

    resp = client.delete(f"/admin/fund-payments/{admin_fund_payment}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd worker && python3 -m pytest tests/test_admin_api.py -v`
Expected: `404 Not Found` on every request (route doesn't exist yet) — assertions fail with `assert 404 == 200`.

- [ ] **Step 3: Implement `worker/admin.py`**

Create `worker/admin.py`:

```python
"""Router admin: list/edit/soft-delete/restore de transacciones ya persistidas.

Sin autenticación (igual que el resto del worker): solo alcanzable en la red
local del Mac mini. Ver docs/superpowers/specs/2026-07-11-admin-crud-design.md.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import admin_db

router = APIRouter(prefix="/admin", tags=["admin"])


class ReceiptUpdate(BaseModel):
    total: float | None = None
    issued_date: date | None = None


class LineItemUpdate(BaseModel):
    unit_price: float | None = None
    qty: float | None = None
    line_total: float | None = None
    category_id: int | None = None


class IncomeUpdate(BaseModel):
    amount: float | None = None
    category_id: int | None = None
    issued_date: date | None = None
    raw_text: str | None = None


class FundPaymentUpdate(BaseModel):
    amount: float | None = None
    category_id: int | None = None
    month: date | None = None
    detail: str | None = None


def _or_404(row: dict | None) -> dict:
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return row


@router.get("/categories")
def list_categories() -> list[dict]:
    return admin_db.list_categories()


@router.get("/receipts")
def list_receipts(month: str | None = None) -> list[dict]:
    return admin_db.list_receipts(month)


@router.get("/receipts/{receipt_id}/items")
def list_receipt_items(receipt_id: int) -> list[dict]:
    return admin_db.list_receipt_items(receipt_id)


@router.patch("/receipts/{receipt_id}")
def update_receipt(receipt_id: int, payload: ReceiptUpdate) -> dict:
    return _or_404(admin_db.update_receipt(receipt_id, payload.total, payload.issued_date))


@router.delete("/receipts/{receipt_id}")
def delete_receipt(receipt_id: int) -> dict:
    return _or_404(admin_db.soft_delete_receipt(receipt_id))


@router.post("/receipts/{receipt_id}/restore")
def restore_receipt(receipt_id: int) -> dict:
    return _or_404(admin_db.restore_receipt(receipt_id))


@router.patch("/line-items/{item_id}")
def update_line_item(item_id: int, payload: LineItemUpdate) -> dict:
    return _or_404(admin_db.update_line_item(
        item_id, payload.unit_price, payload.qty, payload.line_total, payload.category_id
    ))


@router.delete("/line-items/{item_id}")
def delete_line_item(item_id: int) -> dict:
    return _or_404(admin_db.soft_delete_line_item(item_id))


@router.post("/line-items/{item_id}/restore")
def restore_line_item(item_id: int) -> dict:
    return _or_404(admin_db.restore_line_item(item_id))


@router.get("/incomes")
def list_incomes(month: str | None = None) -> list[dict]:
    return admin_db.list_incomes(month)


@router.patch("/incomes/{income_id}")
def update_income(income_id: int, payload: IncomeUpdate) -> dict:
    return _or_404(admin_db.update_income(
        income_id, payload.amount, payload.category_id, payload.issued_date, payload.raw_text
    ))


@router.delete("/incomes/{income_id}")
def delete_income(income_id: int) -> dict:
    return _or_404(admin_db.soft_delete_income(income_id))


@router.post("/incomes/{income_id}/restore")
def restore_income(income_id: int) -> dict:
    return _or_404(admin_db.restore_income(income_id))


@router.get("/fund-payments")
def list_fund_payments(month: str | None = None) -> list[dict]:
    return admin_db.list_fund_payments(month)


@router.patch("/fund-payments/{payment_id}")
def update_fund_payment(payment_id: int, payload: FundPaymentUpdate) -> dict:
    return _or_404(admin_db.update_fund_payment(
        payment_id, payload.amount, payload.category_id, payload.month, payload.detail
    ))


@router.delete("/fund-payments/{payment_id}")
def delete_fund_payment(payment_id: int) -> dict:
    return _or_404(admin_db.soft_delete_fund_payment(payment_id))


@router.post("/fund-payments/{payment_id}/restore")
def restore_fund_payment(payment_id: int) -> dict:
    return _or_404(admin_db.restore_fund_payment(payment_id))
```

- [ ] **Step 4: Mount the router in `worker/app.py`**

In `worker/app.py`, change line 14 from:

```python
import db
```

to:

```python
import db
from admin import router as admin_router
```

Then, right after `app = FastAPI(title="fortunia-worker", version="0.3.0")` (line 22), add:

```python
app.include_router(admin_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd worker && python3 -m pytest tests/test_admin_api.py tests/test_admin_db.py -v`
Expected: all `PASS`.

- [ ] **Step 6: Run the full worker test suite to check for regressions**

Run: `cd worker && python3 -m pytest -v`
Expected: all `PASS`, no regressions in `test_intent.py`, `test_rut.py`, `test_text_expense.py`, `test_text_income.py`, `test_fund_db.py`.

- [ ] **Step 7: Manual smoke test against the running container**

Run: `make deploy` (rebuilds worker with the new files), then:

```bash
curl -s http://localhost:8002/admin/categories | python3 -m json.tool | head -5
```
Expected: JSON array of `{"id": ..., "name": ..., "classification": ...}`.

- [ ] **Step 8: Commit**

```bash
git add worker/admin.py worker/app.py worker/tests/test_admin_api.py
git commit -m "feat(worker): mount /admin CRUD router (receipts, line-items, incomes, fund-payments)"
```

---

## Task 5: Exclude soft-deleted rows from dashboard queries

**Files:**
- Modify: `dashboard/queries.py` (6 query functions)

**Interfaces:**
- Consumes: `line_items.deleted_at`, `fund_payments.deleted_at` from Task 1.
- No new interfaces produced — this task only tightens existing `WHERE`/`JOIN` clauses so a soft-deleted line item or fund payment stops appearing in dashboard reads, matching how `receipts.deleted_at`/`incomes.deleted_at` are already handled.

- [ ] **Step 1: Add `li.deleted_at IS NULL` to the `kpis()` items subquery**

In `dashboard/queries.py`, inside `kpis()` (around line 65-69), change:

```python
          COALESCE((
            SELECT COUNT(*) FROM line_items li
            JOIN receipts r2 ON r2.id = li.receipt_id
            WHERE r2.deleted_at IS NULL AND r2.fund_category_id IS NULL
              AND to_char(COALESCE(r2.issued_date, r2.created_at::date), 'YYYY-MM') = %(m)s
          ), 0)                                                      AS items
```

to:

```python
          COALESCE((
            SELECT COUNT(*) FROM line_items li
            JOIN receipts r2 ON r2.id = li.receipt_id
            WHERE r2.deleted_at IS NULL AND li.deleted_at IS NULL AND r2.fund_category_id IS NULL
              AND to_char(COALESCE(r2.issued_date, r2.created_at::date), 'YYYY-MM') = %(m)s
          ), 0)                                                      AS items
```

- [ ] **Step 2: Add the same filter to `recent_receipts()`'s item count**

In `recent_receipts()` (around line 109), change:

```python
               (SELECT COUNT(*) FROM line_items li WHERE li.receipt_id = r.id) AS items
```

to:

```python
               (SELECT COUNT(*) FROM line_items li WHERE li.receipt_id = r.id AND li.deleted_at IS NULL) AS items
```

- [ ] **Step 3: Filter `receipts_by_category()`**

In `receipts_by_category()` (around line 127-128), change the `FROM`/`JOIN`:

```python
        FROM line_items li
        JOIN receipts r ON r.id = li.receipt_id AND r.deleted_at IS NULL
```

to:

```python
        FROM line_items li
        JOIN receipts r ON r.id = li.receipt_id AND r.deleted_at IS NULL
        WHERE li.deleted_at IS NULL
```

Since this function already has a `WHERE` clause further down (`WHERE to_char(...) = %(m)s AND COALESCE(ro.root_name, ...) = %(root)s`), merge instead — change the existing:

```python
        WHERE to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s
          AND COALESCE(ro.root_name, 'Sin categoria') = %(root)s
```

to:

```python
        WHERE li.deleted_at IS NULL
          AND to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s
          AND COALESCE(ro.root_name, 'Sin categoria') = %(root)s
```

(Do not add a second, separate `WHERE` — there is only one per query.)

- [ ] **Step 4: Filter `receipt_detail()`'s items_sql**

In `receipt_detail()` (around line 147-155), change:

```python
    items_sql = """
        SELECT li.line_no, li.raw_text, li.normalized_name, li.qty,
               li.unit_price, li.line_total,
               COALESCE(c.name, 'Sin categoria') AS category
        FROM line_items li
        LEFT JOIN categories c ON c.id = li.category_id
        WHERE li.receipt_id = %(id)s
        ORDER BY li.line_no
    """
```

to:

```python
    items_sql = """
        SELECT li.line_no, li.raw_text, li.normalized_name, li.qty,
               li.unit_price, li.line_total,
               COALESCE(c.name, 'Sin categoria') AS category
        FROM line_items li
        LEFT JOIN categories c ON c.id = li.category_id
        WHERE li.receipt_id = %(id)s AND li.deleted_at IS NULL
        ORDER BY li.line_no
    """
```

- [ ] **Step 5: Filter `line_items_filter()`**

In `line_items_filter()` (around line 294), change:

```python
    where = ["r.deleted_at IS NULL", "to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s"]
```

to:

```python
    where = ["r.deleted_at IS NULL", "li.deleted_at IS NULL",
             "to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s"]
```

- [ ] **Step 6: Filter `fund_payments_for_month()`'s ranked CTE**

In `fund_payments_for_month()` (around line 344-346), change:

```python
            FROM fund_payments fp
            JOIN categories c ON c.id = fp.category_id
            WHERE fp.month = %(m)s::date
```

to:

```python
            FROM fund_payments fp
            JOIN categories c ON c.id = fp.category_id
            WHERE fp.month = %(m)s::date AND fp.deleted_at IS NULL
```

- [ ] **Step 7: Verify no dashboard tests regress**

Run: `cd dashboard && python3 -m pytest tests/ -v`
Expected: all `PASS` (existing `test_admin.py`, `test_fund_card_state.py` are unaffected by these query changes — they don't hit the DB).

- [ ] **Step 8: Manual end-to-end verification**

With `make deploy` running and Task 4's `admin_fund_payment`-style row already cleaned up, do a real round-trip:

```bash
# 1. Register a fund payment via the normal text flow
curl -s -X POST http://localhost:8002/text -H "Content-Type: application/json" \
  -d '{"text":"pague 15000 en bencina"}' | python3 -m json.tool

# 2. Find its id and soft-delete it via the new admin endpoint
curl -s "http://localhost:8002/admin/fund-payments?month=$(date +%Y-%m)" | python3 -m json.tool
curl -s -X DELETE http://localhost:8002/admin/fund-payments/<id_from_above> | python3 -m json.tool

# 3. Confirm the dashboard's fund view no longer counts it
open http://localhost:8001/
```
Expected: the Gasolina fund card's "pagado" amount drops back by 15.000 after the delete.

- [ ] **Step 9: Commit**

```bash
git add dashboard/queries.py
git commit -m "fix(dashboard): exclude soft-deleted line_items/fund_payments from reads"
```

---

## Task 6: Postman collection

**Files:**
- Create: `postman/fortunia-admin.postman_collection.json`

**Interfaces:**
- Consumes: the HTTP contract from Task 4 (`/admin/*` routes on `worker/app.py`, mounted at `http://localhost:8002`).
- No code interfaces — this is a static JSON artifact for Postman import.

- [ ] **Step 1: Create the collection file**

Create `postman/fortunia-admin.postman_collection.json`:

```json
{
  "info": {
    "name": "Fortunia — Admin CRUD",
    "description": "CRUD administrativo sobre transacciones de Fortunia (receipts, line items, incomes, fund payments). Apunta al worker (:8002). Sin autenticación — solo para uso local del administrador.",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    { "key": "base_url", "value": "http://localhost:8002" },
    { "key": "month", "value": "2026-07" },
    { "key": "id", "value": "1" }
  ],
  "item": [
    {
      "name": "Categories",
      "item": [
        {
          "name": "Listar categorías",
          "request": {
            "method": "GET",
            "url": { "raw": "{{base_url}}/admin/categories", "host": ["{{base_url}}"], "path": ["admin", "categories"] }
          }
        }
      ]
    },
    {
      "name": "Receipts",
      "item": [
        {
          "name": "Listar boletas (filtrado por mes)",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/admin/receipts?month={{month}}",
              "host": ["{{base_url}}"], "path": ["admin", "receipts"],
              "query": [{ "key": "month", "value": "{{month}}" }]
            }
          }
        },
        {
          "name": "Listar boletas (todas)",
          "request": {
            "method": "GET",
            "url": { "raw": "{{base_url}}/admin/receipts", "host": ["{{base_url}}"], "path": ["admin", "receipts"] }
          }
        },
        {
          "name": "Ver ítems de una boleta",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/admin/receipts/{{id}}/items",
              "host": ["{{base_url}}"], "path": ["admin", "receipts", "{{id}}", "items"]
            }
          }
        },
        {
          "name": "Editar boleta (monto/fecha)",
          "request": {
            "method": "PATCH",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": { "mode": "raw", "raw": "{\n  \"total\": 12345,\n  \"issued_date\": \"2026-07-11\"\n}" },
            "url": {
              "raw": "{{base_url}}/admin/receipts/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "receipts", "{{id}}"]
            }
          }
        },
        {
          "name": "Eliminar boleta (soft-delete)",
          "request": {
            "method": "DELETE",
            "url": {
              "raw": "{{base_url}}/admin/receipts/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "receipts", "{{id}}"]
            }
          }
        },
        {
          "name": "Restaurar boleta",
          "request": {
            "method": "POST",
            "url": {
              "raw": "{{base_url}}/admin/receipts/{{id}}/restore",
              "host": ["{{base_url}}"], "path": ["admin", "receipts", "{{id}}", "restore"]
            }
          }
        }
      ]
    },
    {
      "name": "Line Items",
      "item": [
        {
          "name": "Editar ítem (monto/categoría)",
          "request": {
            "method": "PATCH",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": { "mode": "raw", "raw": "{\n  \"line_total\": 5000,\n  \"category_id\": 1\n}" },
            "url": {
              "raw": "{{base_url}}/admin/line-items/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "line-items", "{{id}}"]
            }
          }
        },
        {
          "name": "Eliminar ítem (soft-delete)",
          "request": {
            "method": "DELETE",
            "url": {
              "raw": "{{base_url}}/admin/line-items/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "line-items", "{{id}}"]
            }
          }
        },
        {
          "name": "Restaurar ítem",
          "request": {
            "method": "POST",
            "url": {
              "raw": "{{base_url}}/admin/line-items/{{id}}/restore",
              "host": ["{{base_url}}"], "path": ["admin", "line-items", "{{id}}", "restore"]
            }
          }
        }
      ]
    },
    {
      "name": "Incomes",
      "item": [
        {
          "name": "Listar ingresos (filtrado por mes)",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/admin/incomes?month={{month}}",
              "host": ["{{base_url}}"], "path": ["admin", "incomes"],
              "query": [{ "key": "month", "value": "{{month}}" }]
            }
          }
        },
        {
          "name": "Editar ingreso",
          "request": {
            "method": "PATCH",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": { "mode": "raw", "raw": "{\n  \"amount\": 4402520,\n  \"category_id\": 1,\n  \"issued_date\": \"2026-07-11\",\n  \"raw_text\": \"cobre 4.402.520 de salario\"\n}" },
            "url": {
              "raw": "{{base_url}}/admin/incomes/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "incomes", "{{id}}"]
            }
          }
        },
        {
          "name": "Eliminar ingreso (soft-delete)",
          "request": {
            "method": "DELETE",
            "url": {
              "raw": "{{base_url}}/admin/incomes/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "incomes", "{{id}}"]
            }
          }
        },
        {
          "name": "Restaurar ingreso",
          "request": {
            "method": "POST",
            "url": {
              "raw": "{{base_url}}/admin/incomes/{{id}}/restore",
              "host": ["{{base_url}}"], "path": ["admin", "incomes", "{{id}}", "restore"]
            }
          }
        }
      ]
    },
    {
      "name": "Fund Payments",
      "item": [
        {
          "name": "Listar pagos del fondo (filtrado por mes)",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/admin/fund-payments?month={{month}}",
              "host": ["{{base_url}}"], "path": ["admin", "fund-payments"],
              "query": [{ "key": "month", "value": "{{month}}" }]
            }
          }
        },
        {
          "name": "Editar pago del fondo",
          "request": {
            "method": "PATCH",
            "header": [{ "key": "Content-Type", "value": "application/json" }],
            "body": { "mode": "raw", "raw": "{\n  \"amount\": 804625,\n  \"category_id\": 1,\n  \"month\": \"2026-07-01\",\n  \"detail\": \"crédito hipotecario\"\n}" },
            "url": {
              "raw": "{{base_url}}/admin/fund-payments/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "fund-payments", "{{id}}"]
            }
          }
        },
        {
          "name": "Eliminar pago del fondo (soft-delete)",
          "request": {
            "method": "DELETE",
            "url": {
              "raw": "{{base_url}}/admin/fund-payments/{{id}}",
              "host": ["{{base_url}}"], "path": ["admin", "fund-payments", "{{id}}"]
            }
          }
        },
        {
          "name": "Restaurar pago del fondo",
          "request": {
            "method": "POST",
            "url": {
              "raw": "{{base_url}}/admin/fund-payments/{{id}}/restore",
              "host": ["{{base_url}}"], "path": ["admin", "fund-payments", "{{id}}", "restore"]
            }
          }
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Validate the JSON is well-formed**

Run: `python3 -m json.tool postman/fortunia-admin.postman_collection.json > /dev/null && echo OK`
Expected: `OK`.

- [ ] **Step 3: Smoke-test one request per folder against the running worker**

With `make deploy` up (Task 4 already applied):

```bash
curl -s http://localhost:8002/admin/categories | python3 -m json.tool | head -3
curl -s http://localhost:8002/admin/receipts | python3 -m json.tool | head -3
curl -s http://localhost:8002/admin/incomes | python3 -m json.tool | head -3
curl -s http://localhost:8002/admin/fund-payments | python3 -m json.tool | head -3
```
Expected: all four return valid JSON (arrays, possibly empty `[]` if no data yet — not a 404 or 500).

- [ ] **Step 4: Commit**

```bash
git add postman/fortunia-admin.postman_collection.json
git commit -m "docs: Postman collection for the admin CRUD API"
```

---

## Final verification

- [ ] Run `cd worker && python3 -m pytest -v` — full worker suite passes.
- [ ] Run `cd dashboard && python3 -m pytest tests/ -v` — full dashboard suite passes.
- [ ] Open `http://localhost:8001/` and confirm the dashboard renders normally (no template errors from the query changes in Task 5).
- [ ] Import `postman/fortunia-admin.postman_collection.json` into Postman and run the "Listar" request in each folder — all return 200.
