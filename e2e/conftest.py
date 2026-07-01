"""Fixtures E2E. Lee URLs de env (defaults compose) y un cliente HTTP al worker
para simular el mensaje de Telegram (openclaw -> worker /text)."""
import os

import httpx
import pytest

DASH = os.environ.get("DASHBOARD_URL", "http://localhost:8001")
WORKER = os.environ.get("WORKER_URL", "http://localhost:8002")


@pytest.fixture(scope="session")
def dashboard_url() -> str:
    return DASH


@pytest.fixture(scope="session")
def _skip_if_down():
    try:
        httpx.get(f"{DASH}/health", timeout=3).raise_for_status()
        httpx.get(f"{WORKER}/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("Servicios no disponibles — levanta con `make deploy`")


@pytest.fixture
def telegram(_skip_if_down):
    """Simula un mensaje de Telegram posteando texto libre al worker /text."""
    def _send(text: str) -> dict:
        r = httpx.post(f"{WORKER}/text", json={"text": text}, timeout=15)
        r.raise_for_status()
        return r.json()
    return _send
