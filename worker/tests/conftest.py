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
