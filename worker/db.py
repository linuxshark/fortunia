"""Postgres access (psycopg3). Merchant upsert + idempotent receipt persist."""
from __future__ import annotations

import psycopg
from psycopg import errors
from psycopg.rows import dict_row

from config import settings

RECEIPT_COLS = (
    "merchant_id", "doc_type", "tipo_dte", "folio", "rut_emisor", "rut_receptor",
    "issued_date", "net", "tax", "total", "ted_total", "header_source",
    "validation_status", "source_image_path", "image_sha256",
    "ocr_engine", "ocr_confidence", "ocr_raw_text",
)


def connect() -> psycopg.Connection:
    return psycopg.connect(settings.dsn, row_factory=dict_row)


def healthy() -> bool:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False


def _upsert_merchant(cur, rut: str | None, name: str | None) -> int | None:
    if rut:
        cur.execute(
            """
            INSERT INTO merchants (rut, name, normalized_name)
            VALUES (%s, %s, upper(%s))
            ON CONFLICT (rut) DO UPDATE
              SET name = COALESCE(EXCLUDED.name, merchants.name)
            RETURNING id
            """,
            (rut, name or rut, name or rut),
        )
        return cur.fetchone()["id"]
    if name:
        cur.execute(
            "INSERT INTO merchants (name, normalized_name) VALUES (%s, upper(%s)) RETURNING id",
            (name, name),
        )
        return cur.fetchone()["id"]
    return None


def persist(result: dict) -> tuple[int | None, bool]:
    """Insert merchant + receipt (idempotent) + line items.

    Returns (receipt_id, created). created=False means the receipt already
    existed (same image hash, or same rut+folio+doc_type).
    """
    with connect() as conn, conn.cursor() as cur:
        try:
            merchant_id = _upsert_merchant(
                cur, result.get("rut_emisor"), result.get("merchant_name")
            )

            row = {k: result.get(k) for k in RECEIPT_COLS}
            row["merchant_id"] = merchant_id
            cols = ", ".join(RECEIPT_COLS)
            ph = ", ".join(f"%({c})s" for c in RECEIPT_COLS)
            cur.execute(
                f"""
                INSERT INTO receipts ({cols}) VALUES ({ph})
                ON CONFLICT (image_sha256) DO NOTHING
                RETURNING id
                """,
                row,
            )
            got = cur.fetchone()
            if got is None:
                conn.rollback()
                return None, False           # duplicate image
            receipt_id = got["id"]

            items = result.get("line_items") or []
            if items:
                cur.executemany(
                    """
                    INSERT INTO line_items
                        (receipt_id, line_no, raw_text, normalized_name,
                         category_id, category_source, qty, unit_price, line_total)
                    VALUES
                        (%(receipt_id)s, %(line_no)s, %(raw_text)s, %(normalized_name)s,
                         %(category_id)s, %(category_source)s, %(qty)s, %(unit_price)s, %(line_total)s)
                    """,
                    [{"receipt_id": receipt_id, **it} for it in items],
                )
            conn.commit()
            return receipt_id, True
        except errors.UniqueViolation:
            conn.rollback()
            return None, False               # same rut+folio+doc_type already stored


def persist_income(parsed: dict, category_id: int | None) -> tuple[int, bool]:
    """Insert a row into incomes. No idempotency — same income on different days is valid."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO incomes (category_id, amount, source_text, raw_text, issued_date)
            VALUES (%(category_id)s, %(amount)s, %(source_text)s, %(raw_text)s, CURRENT_DATE)
            RETURNING id
            """,
            {
                "category_id": category_id,
                "amount": parsed["amount"],
                "source_text": parsed["source_text"],
                "raw_text": parsed["raw"],
            },
        )
        income_id = cur.fetchone()["id"]
        conn.commit()
    return income_id, True
