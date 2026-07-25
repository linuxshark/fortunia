"""Fixtures de tests DB-integration. Conecta con el mismo dsn que usa writes.py
(rol fortunia_ro, que tiene INSERT/UPDATE solo sobre fund_monthly).

Corren contra la Postgres de compose (localhost). Precondición: `make deploy`
levantado; si no responde, se skipean.
"""
import sys
from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from config import settings, REPO_ROOT  # noqa: E402


class _OwnerSettings(BaseSettings):
    """Credenciales del owner (RW), solo para limpiar filas de test.

    fortunia_ro tiene SELECT/INSERT/UPDATE sobre fund_monthly pero no DELETE
    (ver db/03_ro_role.sh); la limpieza de filas de test necesita el owner.
    """

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    postgres_user: str = "boleta"
    postgres_password: str = "change_me"
    postgres_db: str = "boletas"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@pytest.fixture
def db():
    try:
        conn = psycopg.connect(settings.dsn, connect_timeout=2, row_factory=dict_row)
    except Exception:
        pytest.skip("DB no disponible — levanta con `make deploy` para tests DB")
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture
def clean_fund_plan(db):
    """Borra filas de fund_monthly creadas por los tests (meses 2099-01/2099-02).

    Usa una conexión aparte con credenciales de owner porque fortunia_ro (la
    del fixture `db`) no tiene GRANT DELETE sobre fund_monthly.
    """
    yield
    owner_conn = psycopg.connect(_OwnerSettings().dsn, connect_timeout=2)
    owner_conn.autocommit = True
    try:
        with owner_conn.cursor() as cur:
            cur.execute("DELETE FROM fund_monthly WHERE month IN (DATE '2099-01-01', DATE '2099-02-01')")
    finally:
        owner_conn.close()
