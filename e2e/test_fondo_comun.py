"""E2E Fondo Común: declarar pago por 'Telegram' marca la categoría pagada,
baja la barra; el presupuesto es editable mes a mes; las barras de ingreso
muestran fuentes."""
import re

from playwright.sync_api import Page, expect


def _bar_width(page: Page) -> float:
    style = page.locator(".fund-bar-fill").get_attribute("style") or ""
    m = re.search(r"width:\s*([\d.]+)%", style)
    return float(m.group(1)) if m else 0.0


def test_pago_telegram_marca_pagado_y_consume_fondo(page: Page, dashboard_url, telegram, _skip_if_down):
    page.goto(dashboard_url)
    expect(page.get_by_text("Fondo Común del hogar")).to_be_visible()
    before = _bar_width(page)

    resp = telegram("pagué 30000 de agua")
    assert resp["routed_to"] == "fund"
    assert resp["category"] == "Agua"

    page.goto(dashboard_url)
    agua_card = page.locator(".fund-card", has=page.get_by_text("Agua", exact=True))
    expect(agua_card.locator(".badge.paid")).to_be_visible()
    assert _bar_width(page) >= before


def test_idempotente_reportar_dos_veces_no_duplica(page: Page, dashboard_url, telegram, _skip_if_down):
    telegram("pagué 55000 de electricidad")
    telegram("pagué 60000 de electricidad")
    page.goto(dashboard_url)
    luz_card = page.locator(".fund-card", has=page.get_by_text("Electricidad", exact=True))
    expect(luz_card.get_by_text("Pagado: $60.000")).to_be_visible()


def test_editar_presupuesto_mes_a_mes(page: Page, dashboard_url, _skip_if_down):
    page.goto(dashboard_url)
    internet_card = page.locator(".fund-card", has=page.get_by_text("Internet", exact=True))
    inp = internet_card.locator("input[name='amount']")
    inp.fill("34000")
    inp.dispatch_event("change")
    page.wait_for_timeout(1200)
    page.goto(dashboard_url)
    internet_card = page.locator(".fund-card", has=page.get_by_text("Internet", exact=True))
    expect(internet_card.locator("input[name='amount']")).to_have_value("34000")


def test_barras_de_ingreso_por_fuente(page: Page, dashboard_url, telegram, _skip_if_down):
    import httpx, os
    httpx.post(
        f"{os.environ.get('WORKER_URL','http://localhost:8002')}/income",
        json={"text": "cobré 4400000 de sueldo"}, timeout=15,
    ).raise_for_status()
    page.goto(dashboard_url)
    expect(page.get_by_text("Ingresos del mes")).to_be_visible()
    expect(page.locator("#incomeChart")).to_be_visible()
