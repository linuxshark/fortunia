"""Dashboard de gastos fortunia (server-rendered, read-only).

FastAPI + Jinja2 + HTMX + Chart.js. Lee Postgres con rol fortunia_ro.
Corre interno en :8000; compose lo publica en host :8001.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import queries as q
from config import settings

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="fortunia-dashboard", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# Paleta determinista por categoría raíz (categories.color está casi vacío en la DB)
PALETTE = {
    "Alimentos": "#2563eb",
    "Bebidas": "#16a34a",
    "Aseo y Limpieza": "#0891b2",
    "Cuidado Personal": "#db2777",
    "Mascotas": "#ca8a04",
    "Otros": "#7c3aed",
    "Sin categoria": "#94a3b8",
}
_FALLBACK = ["#ef4444", "#f97316", "#84cc16", "#06b6d4", "#8b5cf6", "#ec4899", "#14b8a6"]


def color_for(name: str) -> str:
    if name in PALETTE:
        return PALETTE[name]
    return _FALLBACK[sum(map(ord, name)) % len(_FALLBACK)]


FUND_EMOJI = {
    "Agua": "💧", "Electricidad": "⚡", "Internet": "📡", "Supermercado": "🛒",
    "Arriendo/Dividendo": "🏠", "Jardín infantil": "🧒", "Auto (cuota)": "🚗",
    "Restaurantes": "🍽️", "Remesas Venezuela": "💸", "GGCC": "🏢",
    "Gasolina": "⛽", "TAG": "🛣️", "Ahorro": "🐷",
}


def emoji_for(name: str) -> str:
    return FUND_EMOJI.get(name, "•")


def _clp(value) -> str:
    try:
        return "$" + f"{int(round(float(value))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


templates.env.filters["clp"] = _clp
templates.env.globals["color_for"] = color_for
templates.env.globals["emoji_for"] = emoji_for


def resolve_month(month: str | None, months: list[str]) -> str:
    if month and month in months:
        return month
    if month:                       # mes pedido sin datos: respétalo igual
        return month
    cur = q.current_month()
    if cur in months or not months:
        return cur
    return months[0]                # último mes con datos


def _overview_ctx(request: Request, month: str | None) -> dict:
    months = q.months_available()
    month = resolve_month(month, months)
    cats = q.category_breakdown(month)
    inc_kpis = q.income_kpis(month)
    inc_cats = q.income_by_category(month)
    expense_kpis = q.kpis(month)
    fund_rows = q.fund_status(month)
    fund_tot = q.fund_totals(month)
    inc_total = float(inc_kpis["total"])
    exp_total = float(expense_kpis["total"])
    balance_pct = int(100 * exp_total / inc_total) if inc_total > 0 else 0
    return {
        "request": request,
        "month": month,
        "months": months,
        "kpis": expense_kpis,
        "income_kpis": inc_kpis,
        "income_categories": inc_cats,
        "income_chart_labels": [c["category"] for c in inc_cats],
        "income_chart_data": [float(c["total"]) for c in inc_cats],
        "balance_pct": min(balance_pct, 100),
        "fund_rows": fund_rows,
        "fund_totals": fund_tot,
        "categories": cats,
        "merchants": q.top_merchants(month),
        "receipts": q.recent_receipts(month),
        "chart_labels": [c["category"] for c in cats],
        "chart_data": [float(c["total"]) for c in cats],
        "chart_colors": [color_for(c["category"]) for c in cats],
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "db": q.healthy()}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, month: str | None = None):
    return templates.TemplateResponse(request, "index.html", _overview_ctx(request, month))


@app.get("/partials/overview", response_class=HTMLResponse)
def overview_partial(request: Request, month: str | None = None):
    return templates.TemplateResponse(request, "_overview.html", _overview_ctx(request, month))


@app.get("/category/{root}", response_class=HTMLResponse)
def category(request: Request, root: str, month: str | None = None):
    months = q.months_available()
    month = resolve_month(month, months)
    rows = q.receipts_by_category(root, month)
    total = sum(float(r["line_total"] or 0) for r in rows)
    return templates.TemplateResponse(request, "category.html", {
        "request": request, "root": root, "month": month, "months": months,
        "rows": rows, "total": total,
    })


@app.get("/receipt/{receipt_id}", response_class=HTMLResponse)
def receipt(request: Request, receipt_id: int):
    header, items = q.receipt_detail(receipt_id)
    return templates.TemplateResponse(request, "receipt.html", {
        "request": request, "header": header, "items": items,
    })


@app.get("/incomes", response_class=HTMLResponse)
def incomes(request: Request, month: str | None = None):
    months = q.months_available()
    month = resolve_month(month, months)
    rows = q.recent_incomes(month)
    total = sum(float(r["amount"] or 0) for r in rows)
    return templates.TemplateResponse(request, "incomes.html", {
        "request": request, "month": month, "months": months,
        "rows": rows, "total": total,
    })


@app.get("/expenses", response_class=HTMLResponse)
def expenses(request: Request, month: str | None = None,
             category: str | None = None, merchant: str | None = None):
    months = q.months_available()
    month = resolve_month(month, months)
    rows = q.line_items_filter(month, category, merchant)
    cats = q.category_breakdown(month)
    total = sum(float(r["line_total"] or 0) for r in rows)
    return templates.TemplateResponse(request, "expenses.html", {
        "request": request, "month": month, "months": months,
        "category": category, "merchant": merchant,
        "rows": rows, "total": total,
        "all_categories": [c["category"] for c in cats],
    })


@app.get("/image/{sha}")
def image(sha: str):
    # Solo nombre de archivo (sha hex) — evita traversal
    safe = "".join(ch for ch in sha if ch.isalnum())
    path = settings.image_dir / f"{safe}.bin"
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="image/jpeg")
