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
