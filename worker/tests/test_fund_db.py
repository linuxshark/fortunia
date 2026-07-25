import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from categorize import categorize_shared, resolve_shared  # noqa: E402
from db import shared_category_id_by_name, upsert_fund_payment  # noqa: E402

MONTH = date(2099, 1, 1)


def test_shared_category_id_by_name_resuelve(db):
    """Mapea el nombre que Gemini asigna a una boleta al id de la categoría shared."""
    assert shared_category_id_by_name("Alimentos") is not None
    # case-insensitive
    assert shared_category_id_by_name("alimentos") == shared_category_id_by_name("Alimentos")


def test_shared_category_id_by_name_none(db):
    assert shared_category_id_by_name(None) is None
    assert shared_category_id_by_name("") is None
    assert shared_category_id_by_name("Farmacia") is None  # no es categoría compartida


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


def test_categorize_shared_vocabulario_natural(db):
    """El vocabulario con que uno escribe por Telegram debe rutear al Fondo.

    Regresión: "gasté 806.770 en alimentos" caía al flujo de boleta de texto
    porque 'alimentos' —el nombre mismo de la categoría— no era alias."""
    for texto, esperado in (
        ("alimentos", "Alimentos"),
        ("comida", "Alimentos"),
        ("mercado", "Alimentos"),
        ("feria", "Alimentos"),
        ("almuerzo", "Restaurantes"),
        ("cena", "Restaurantes"),
    ):
        cat_id, norm, source = categorize_shared(texto)
        assert cat_id is not None, f"{texto!r} no ruteó al fondo"
        assert norm == esperado, f"{texto!r} → {norm!r}, esperaba {esperado!r}"
        assert source == "rule"


def test_resolve_shared_fallback_por_nombre_de_categoria(db):
    """Todo nombre de categoría shared debe rutear al fondo, tenga alias o no.

    Cierra el agujero de diseño: shared_category_id_by_name() se usaba solo en
    el flujo OCR, así que escribir el nombre literal funcionaba por foto pero
    no por texto."""
    with db.cursor() as cur:
        cur.execute("SELECT id, name FROM categories WHERE classification = 'shared'")
        shared = cur.fetchall()

    for cat_id, name in shared:
        got_id, norm, source = resolve_shared(name)
        assert got_id == cat_id, f"{name!r} → {got_id}, esperaba {cat_id}"
        assert norm == name
        assert source in ("rule", "name")


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
