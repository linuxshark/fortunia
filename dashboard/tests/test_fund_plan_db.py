import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from writes import seed_month_from, set_budget  # noqa: E402

SRC = "2099-01"
DST = "2099-02"


def test_seed_month_from_copia_presupuestos(db, clean_fund_plan):
    set_budget(_agua_id(db), SRC, 30000)
    seed_month_from(SRC, DST)
    with db.cursor() as cur:
        cur.execute(
            "SELECT fm.budget_amount FROM fund_monthly fm "
            "JOIN categories c ON c.id = fm.category_id "
            "WHERE c.name = 'Agua' AND fm.month = DATE '2099-02-01'"
        )
        row = cur.fetchone()
        assert row is not None
        assert int(row["budget_amount"]) == 30000


def test_seed_month_from_es_idempotente_no_pisa_ediciones(db, clean_fund_plan):
    agua_id = _agua_id(db)
    set_budget(agua_id, SRC, 30000)
    seed_month_from(SRC, DST)
    set_budget(agua_id, DST, 99000)  # edición manual en el mes destino
    seed_month_from(SRC, DST)        # re-sembrar no debe pisarla

    with db.cursor() as cur:
        cur.execute(
            "SELECT budget_amount FROM fund_monthly WHERE category_id = %s AND month = DATE '2099-02-01'",
            (agua_id,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1              # sin duplicados
        assert int(rows[0]["budget_amount"]) == 99000


def _agua_id(db):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM categories WHERE name = 'Agua' AND classification = 'shared'")
        return cur.fetchone()["id"]
