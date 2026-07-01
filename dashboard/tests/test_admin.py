import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_admin_page_lists_backups(monkeypatch):
    monkeypatch.setattr(appmod, "_backup_get", lambda path: [
        {"name": "db-20260701-030000.dump", "size": 1234, "ts": "2026-07-01T03:00:00", "tier": "diario"},
    ])
    monkeypatch.setattr(appmod, "_backup_health", lambda: {"disk_ok": True})
    client = TestClient(appmod.app)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "db-20260701-030000.dump" in r.text


def test_admin_restore_requires_confirm_word(monkeypatch):
    called = {}
    monkeypatch.setattr(appmod, "_backup_post", lambda path, data=None: called.setdefault("data", data) or {"restored": data["name"]})
    monkeypatch.setattr(appmod, "_backup_get", lambda path: [])
    monkeypatch.setattr(appmod, "_backup_health", lambda: {"disk_ok": True})
    client = TestClient(appmod.app)
    # confirm incorrecto -> no llama a la API, 400
    r = client.post("/admin/restore", data={"name": "db-x.dump", "confirm": "nope"})
    assert r.status_code == 400
    assert "data" not in called
    # confirm correcto -> llama
    r = client.post("/admin/restore", data={"name": "db-x.dump", "confirm": "RESTAURAR"})
    assert r.status_code == 200
    assert called["data"] == {"name": "db-x.dump"}
