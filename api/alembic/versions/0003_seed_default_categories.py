"""Seed default categories.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

DEFAULT_CATEGORIES = [
    ("Salario",                    "income",  "{salario,sueldo,remuneracion,pago}"),
    ("Comida",                     "expense", "{comida,supermercado,almacen,mercado,groceries}"),
    ("Servicio Agua",              "expense", "{agua,servicio agua,bill agua}"),
    ("Servicio Energía Eléctrica", "expense", "{luz,electricidad,energia electrica,enel,cge}"),
    ("Crédito Hipotecario",        "expense", "{hipoteca,credito hipotecario,dividendo,mortgage}"),
    ("Crédito Consumo",            "expense", "{credito consumo,prestamo consumo,cuota consumo}"),
    ("Crédito Automotriz",         "expense", "{credito auto,credito automotriz,cuota auto,leasing}"),
    ("TDC",                        "expense", "{tdc,tarjeta de credito,tarjeta credito,visa,mastercard,amex}"),
    ("Restaurantes",               "expense", "{restaurante,restaurant,comida rapida,fast food,delivery,uber eats,rappi, delivery}"),
    ("Estacionamiento",            "expense", "{estacionamiento,parking,parqueo}"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, applicable_to, keywords in DEFAULT_CATEGORIES:
        conn.execute(
            sa.text(
                """
                INSERT INTO categories (name, applicable_to, keywords, created_at)
                VALUES (:name, :applicable_to, :keywords, NOW())
                ON CONFLICT (name) DO NOTHING
                """
            ),
            {"name": name, "applicable_to": applicable_to, "keywords": keywords},
        )


def downgrade() -> None:
    conn = op.get_bind()
    names = [c[0] for c in DEFAULT_CATEGORIES]
    conn.execute(
        sa.text("DELETE FROM categories WHERE name = ANY(:names)"),
        {"names": names},
    )
