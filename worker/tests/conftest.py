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
    """Borra filas de fund_monthly/fund_payments creadas por los tests (mes 2099-01)."""
    yield
    with db.cursor() as cur:
        cur.execute("DELETE FROM fund_payments WHERE month = DATE '2099-01-01'")
        cur.execute("DELETE FROM fund_monthly WHERE month = DATE '2099-01-01'")


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
