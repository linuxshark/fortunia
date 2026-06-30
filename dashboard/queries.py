"""Capa de lectura (psycopg3, dict_row). SOLO SELECT — rol fortunia_ro.

Reusa las vistas analíticas del esquema (v_monthly_spend_by_category,
v_spend_by_merchant) y arma drill-downs con un CTE recursivo de categorías raíz,
igual que las vistas. El mes se maneja como string 'YYYY-MM'.
"""
from __future__ import annotations

import datetime as _dt

import psycopg
from psycopg.rows import dict_row

from config import settings

# CTE que mapea cada categoría a su raíz (Alimentos > Lacteos > Leche -> Alimentos)
_ROOTS_CTE = """
WITH RECURSIVE roots AS (
  SELECT id, id AS root_id, name AS root_name FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, r.root_id, r.root_name
  FROM categories c JOIN roots r ON c.parent_id = r.id
)
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.dsn, row_factory=dict_row)


def healthy() -> bool:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False


def current_month() -> str:
    return _dt.date.today().strftime("%Y-%m")


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


def kpis(month: str) -> dict:
    sql = """
        SELECT
          COALESCE(SUM(r.total), 0)                                  AS total,
          COUNT(*)                                                   AS receipts,
          COALESCE((
            SELECT COUNT(*) FROM line_items li
            JOIN receipts r2 ON r2.id = li.receipt_id
            WHERE r2.deleted_at IS NULL
              AND to_char(COALESCE(r2.issued_date, r2.created_at::date), 'YYYY-MM') = %(m)s
          ), 0)                                                      AS items
        FROM receipts r
        WHERE r.deleted_at IS NULL AND to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month})
        return cur.fetchone() or {"total": 0, "receipts": 0, "items": 0}


def category_breakdown(month: str) -> list[dict]:
    sql = """
        SELECT category, total
        FROM v_monthly_spend_by_category
        WHERE to_char(month, 'YYYY-MM') = %(m)s
        ORDER BY total DESC
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month})
        return cur.fetchall()


def top_merchants(month: str, limit: int = 10) -> list[dict]:
    sql = """
        SELECT COALESCE(merchant, 'Sin comercio') AS merchant, total
        FROM v_spend_by_merchant
        WHERE to_char(month, 'YYYY-MM') = %(m)s
        ORDER BY total DESC NULLS LAST
        LIMIT %(lim)s
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month, "lim": limit})
        return cur.fetchall()


def recent_receipts(month: str, limit: int = 25) -> list[dict]:
    sql = """
        SELECT r.id, r.issued_date,
               COALESCE(m.name, 'Sin comercio') AS merchant,
               r.total, r.validation_status,
               (SELECT COUNT(*) FROM line_items li WHERE li.receipt_id = r.id) AS items
        FROM receipts r
        LEFT JOIN merchants m ON m.id = r.merchant_id
        WHERE r.deleted_at IS NULL AND to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s
        ORDER BY COALESCE(r.issued_date, r.created_at::date) DESC, r.id DESC
        LIMIT %(lim)s
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month, "lim": limit})
        return cur.fetchall()


def receipts_by_category(root: str, month: str) -> list[dict]:
    sql = _ROOTS_CTE + """
        SELECT r.id AS receipt_id, r.issued_date,
               COALESCE(m.name, 'Sin comercio') AS merchant,
               li.line_no, li.normalized_name, li.raw_text,
               li.qty, li.unit_price, li.line_total
        FROM line_items li
        JOIN receipts r ON r.id = li.receipt_id AND r.deleted_at IS NULL
        LEFT JOIN merchants m ON m.id = r.merchant_id
        LEFT JOIN roots ro ON ro.id = li.category_id
        WHERE to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s
          AND COALESCE(ro.root_name, 'Sin categoria') = %(root)s
        ORDER BY COALESCE(r.issued_date, r.created_at::date) DESC, r.id DESC, li.line_no
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, {"m": month, "root": root})
        return cur.fetchall()


def receipt_detail(receipt_id: int) -> tuple[dict | None, list[dict]]:
    head_sql = """
        SELECT r.*, COALESCE(m.name, 'Sin comercio') AS merchant_name, m.rut AS merchant_rut
        FROM receipts r
        LEFT JOIN merchants m ON m.id = r.merchant_id
        WHERE r.id = %(id)s AND r.deleted_at IS NULL
    """
    items_sql = """
        SELECT li.line_no, li.raw_text, li.normalized_name, li.qty,
               li.unit_price, li.line_total,
               COALESCE(c.name, 'Sin categoria') AS category
        FROM line_items li
        LEFT JOIN categories c ON c.id = li.category_id
        WHERE li.receipt_id = %(id)s
        ORDER BY li.line_no
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(head_sql, {"id": receipt_id})
        header = cur.fetchone()
        if header is None:
            return None, []
        cur.execute(items_sql, {"id": receipt_id})
        return header, cur.fetchall()


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


def line_items_filter(month: str, category: str | None = None,
                      merchant: str | None = None) -> list[dict]:
    where = ["r.deleted_at IS NULL", "to_char(COALESCE(r.issued_date, r.created_at::date), 'YYYY-MM') = %(m)s"]
    params: dict = {"m": month}
    if category:
        where.append("COALESCE(ro.root_name, 'Sin categoria') = %(cat)s")
        params["cat"] = category
    if merchant:
        where.append("COALESCE(m.name, 'Sin comercio') = %(merch)s")
        params["merch"] = merchant
    sql = _ROOTS_CTE + f"""
        SELECT r.id AS receipt_id, r.issued_date,
               COALESCE(m.name, 'Sin comercio') AS merchant,
               COALESCE(ro.root_name, 'Sin categoria') AS category,
               li.normalized_name, li.raw_text, li.qty, li.unit_price, li.line_total
        FROM line_items li
        JOIN receipts r ON r.id = li.receipt_id
        LEFT JOIN merchants m ON m.id = r.merchant_id
        LEFT JOIN roots ro ON ro.id = li.category_id
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(r.issued_date, r.created_at::date) DESC, r.id DESC, li.line_no
    """
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
