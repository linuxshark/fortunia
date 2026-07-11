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
    where = ["1=1"]
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
        WHERE li.receipt_id = %(id)s
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
