import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_db  # noqa: E402


def test_list_receipts_filters_by_month(admin_receipt):
    rows = admin_db.list_receipts("2099-02")
    assert any(r["id"] == admin_receipt for r in rows)


def test_list_receipts_month_no_match(admin_receipt):
    rows = admin_db.list_receipts("2099-01")
    assert all(r["id"] != admin_receipt for r in rows)


def test_list_receipts_no_month_includes_all(admin_receipt):
    rows = admin_db.list_receipts(None)
    assert any(r["id"] == admin_receipt for r in rows)


def test_update_receipt_total(admin_receipt):
    row = admin_db.update_receipt(admin_receipt, total=2500, issued_date=None)
    assert float(row["total"]) == 2500


def test_update_receipt_not_found():
    assert admin_db.update_receipt(999999999, total=1, issued_date=None) is None


def test_soft_delete_and_restore_receipt(admin_receipt):
    deleted = admin_db.soft_delete_receipt(admin_receipt)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_receipt(admin_receipt)
    assert restored["deleted_at"] is None


def test_deleted_receipt_disappears_and_restored_reappears_in_list(admin_receipt):
    admin_db.soft_delete_receipt(admin_receipt)
    rows = admin_db.list_receipts("2099-02")
    assert all(r["id"] != admin_receipt for r in rows)
    admin_db.restore_receipt(admin_receipt)
    rows = admin_db.list_receipts("2099-02")
    assert any(r["id"] == admin_receipt for r in rows)


def test_list_receipt_items(admin_line_item, admin_receipt):
    rows = admin_db.list_receipt_items(admin_receipt)
    assert any(r["id"] == admin_line_item for r in rows)


def test_update_line_item_category(admin_line_item, shared_category_id):
    row = admin_db.update_line_item(
        admin_line_item, unit_price=None, qty=None, line_total=None, category_id=shared_category_id
    )
    assert row["category_id"] == shared_category_id


def test_update_line_item_amount(admin_line_item):
    row = admin_db.update_line_item(
        admin_line_item, unit_price=2000, qty=None, line_total=2000, category_id=None
    )
    assert float(row["line_total"]) == 2000


def test_soft_delete_and_restore_line_item(admin_line_item):
    deleted = admin_db.soft_delete_line_item(admin_line_item)
    assert deleted["deleted_at"] is not None
    restored = admin_db.restore_line_item(admin_line_item)
    assert restored["deleted_at"] is None


def test_deleted_line_item_disappears_and_restored_reappears_in_list(admin_line_item, admin_receipt):
    admin_db.soft_delete_line_item(admin_line_item)
    rows = admin_db.list_receipt_items(admin_receipt)
    assert all(r["id"] != admin_line_item for r in rows)
    admin_db.restore_line_item(admin_line_item)
    rows = admin_db.list_receipt_items(admin_receipt)
    assert any(r["id"] == admin_line_item for r in rows)
