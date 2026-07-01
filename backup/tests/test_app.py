import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod           # noqa: E402
from scheduler import next_run_at  # noqa: E402


def test_next_run_at_today_and_tomorrow():
    tz = ZoneInfo("America/Santiago")
    now = datetime(2026, 7, 1, 1, 0, tzinfo=tz)     # antes de 03:00
    assert next_run_at(now, 3, 0, tz) == datetime(2026, 7, 1, 3, 0, tzinfo=tz)
    now2 = datetime(2026, 7, 1, 5, 0, tzinfo=tz)    # después de 03:00
    assert next_run_at(now2, 3, 0, tz) == datetime(2026, 7, 2, 3, 0, tzinfo=tz)


def test_health_and_backups_endpoints(monkeypatch):
    monkeypatch.setattr(appmod.engine, "list_backups", lambda s: [{"name": "db-x.dump"}])
    monkeypatch.setattr(appmod, "disk_available", lambda d, n: True)
    client = TestClient(appmod.app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["disk_ok"] is True
    r = client.get("/backups")
    assert r.json() == [{"name": "db-x.dump"}]


def test_run_and_restore_endpoints(monkeypatch):
    monkeypatch.setattr(appmod.engine, "run_backup", lambda s: {"file": "db-y.dump", "size": 1, "ts": "t"})
    monkeypatch.setattr(appmod.engine, "restore", lambda s, name: {"restored": name})
    client = TestClient(appmod.app)
    assert client.post("/backups/run").json()["file"] == "db-y.dump"
    assert client.post("/restore", data={"name": "db-y.dump"}).json()["restored"] == "db-y.dump"


def test_restore_bad_name_returns_400(monkeypatch):
    def boom(s, name): raise ValueError("nope")
    monkeypatch.setattr(appmod.engine, "restore", boom)
    client = TestClient(appmod.app)
    assert client.post("/restore", data={"name": "../evil"}).status_code == 400
