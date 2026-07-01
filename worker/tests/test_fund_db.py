import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from categorize import categorize_shared  # noqa: E402
from db import upsert_fund_payment  # noqa: E402

MONTH = date(2099, 1, 1)


def test_categorize_shared_electricidad(db):
    cat_id, norm, source = categorize_shared("electricidad")
    assert cat_id is not None
    assert norm == "Electricidad"
    assert source == "rule"


def test_categorize_shared_luz_alias(db):
    _, norm, _ = categorize_shared("pagué la luz")
    assert norm == "Electricidad"


def test_categorize_shared_no_match(db):
    cat_id, _, source = categorize_shared("pan amasado")
    assert cat_id is None
    assert source == "unmatched"


def test_upsert_fund_payment_inicial(db, clean_fund):
    cat_id, _, _ = categorize_shared("electricidad")
    paid, remaining = upsert_fund_payment(cat_id, MONTH, 55000, "telegram")
    assert int(paid) == 55000
    assert int(remaining) == 0


def test_upsert_fund_payment_idempotente_reemplaza(db, clean_fund):
    """Electricidad es 'replace' (boleta fija): el pago más reciente reemplaza."""
    cat_id, _, _ = categorize_shared("electricidad")
    upsert_fund_payment(cat_id, MONTH, 55000, "telegram")
    paid, _ = upsert_fund_payment(cat_id, MONTH, 60000, "telegram")
    assert int(paid) == 60000
    with db.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM fund_monthly WHERE category_id=%s AND month=%s",
            (cat_id, MONTH),
        )
        assert cur.fetchone()[0] == 1


def test_upsert_fund_payment_restaurantes_suma_y_guarda_detalle(db, clean_fund):
    """Restaurantes es 'sum' (gasto variable): cada comida se acumula, con detalle."""
    cat_id, _, _ = categorize_shared("restaurante")
    upsert_fund_payment(cat_id, MONTH, 15000, "telegram", "KFC")
    paid, _ = upsert_fund_payment(cat_id, MONTH, 20000, "telegram", "Mcdonalds")
    assert int(paid) == 35000
    with db.cursor() as cur:
        cur.execute(
            "SELECT detail, amount FROM fund_payments WHERE category_id=%s AND month=%s ORDER BY id",
            (cat_id, MONTH),
        )
        rows = cur.fetchall()
        assert [r[0] for r in rows] == ["KFC", "Mcdonalds"]
