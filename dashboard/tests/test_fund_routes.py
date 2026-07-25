import sys
from pathlib import Path

from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402


def test_fund_plan_seeds_and_renders_back_face(monkeypatch):
    calls = {}
    monkeypatch.setattr(appmod.writes, "seed_month_from", lambda src, dst: calls.setdefault("seed", (src, dst)))
    monkeypatch.setattr(appmod.q, "fund_plan", lambda month, compare_to: {
        "month": month, "rows": [], "total": 0.0,
    })
    client = TestClient(appmod.app)
    r = client.post("/fund/plan", data={"month": "2026-07"})
    assert r.status_code == 200
    assert calls["seed"] == ("2026-07", "2026-08")


def test_fund_plan_rejects_malformed_month(monkeypatch):
    client = TestClient(appmod.app)
    r = client.post("/fund/plan", data={"month": "not-a-month"})
    assert r.status_code == 400


def test_fund_budget_view_plan_rerenders_plan_partial(monkeypatch):
    monkeypatch.setattr(appmod.writes, "set_budget", lambda *a, **k: None)
    monkeypatch.setattr(appmod.q, "fund_plan", lambda month, compare_to: {
        "month": month, "rows": [], "total": 0.0,
    })
    client = TestClient(appmod.app)
    r = client.post("/fund/budget", data={
        "category_id": "1", "month": "2026-08", "amount": "1000",
        "view": "plan", "compare_to": "2026-07",
    })
    assert r.status_code == 200


def test_fund_budget_default_view_unchanged(monkeypatch):
    monkeypatch.setattr(appmod.writes, "set_budget", lambda *a, **k: None)
    captured = {}

    def fake_response(request, name, context=None, **kw):
        captured["name"] = name
        return HTMLResponse("ok")

    monkeypatch.setattr(appmod.templates, "TemplateResponse", fake_response)
    client = TestClient(appmod.app)
    r = client.post("/fund/budget", data={"category_id": "1", "month": "2026-07", "amount": "1000"})
    assert r.status_code == 200
    assert captured["name"] == "_overview.html"
