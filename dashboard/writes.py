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
