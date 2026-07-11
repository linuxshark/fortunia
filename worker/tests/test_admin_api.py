import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_list_categories_endpoint(client, db):
    resp = client.get("/admin/categories")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_patch_income_not_found(client, db):
    resp = client.patch("/admin/incomes/999999999", json={"amount": 100})
    assert resp.status_code == 404


def test_income_crud_roundtrip(client, db, admin_income):
    resp = client.get("/admin/incomes", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_income for row in resp.json())

    resp = client.patch(f"/admin/incomes/{admin_income}", json={"amount": 700000})
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 700000

    resp = client.delete(f"/admin/incomes/{admin_income}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None

    resp = client.post(f"/admin/incomes/{admin_income}/restore")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is None


def test_receipt_and_line_item_crud_roundtrip(client, db, admin_receipt, admin_line_item):
    resp = client.get("/admin/receipts", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_receipt for row in resp.json())

    resp = client.get(f"/admin/receipts/{admin_receipt}/items")
    assert resp.status_code == 200
    assert any(row["id"] == admin_line_item for row in resp.json())

    resp = client.patch(f"/admin/line-items/{admin_line_item}", json={"line_total": 5000})
    assert resp.status_code == 200
    assert float(resp.json()["line_total"]) == 5000

    resp = client.delete(f"/admin/receipts/{admin_receipt}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None

    resp = client.post(f"/admin/receipts/{admin_receipt}/restore")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is None


def test_fund_payment_crud_roundtrip(client, db, admin_fund_payment):
    resp = client.get("/admin/fund-payments", params={"month": "2099-02"})
    assert resp.status_code == 200
    assert any(row["id"] == admin_fund_payment for row in resp.json())

    resp = client.patch(f"/admin/fund-payments/{admin_fund_payment}", json={"amount": 45000})
    assert resp.status_code == 200
    assert float(resp.json()["amount"]) == 45000

    resp = client.delete(f"/admin/fund-payments/{admin_fund_payment}")
    assert resp.status_code == 200
    assert resp.json()["deleted_at"] is not None
