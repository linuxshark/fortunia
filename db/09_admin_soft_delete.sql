-- db/09_admin_soft_delete.sql — Soft-delete para el panel admin. Idempotente.
--
-- receipts e incomes ya tienen deleted_at. fund_payments y line_items no lo
-- tenían porque nada los borraba hasta ahora. El panel admin (worker /admin/*)
-- necesita poder "deshacer" un borrado, así que se usa soft-delete en todo:
-- ver docs/superpowers/specs/2026-07-11-admin-crud-design.md.

ALTER TABLE fund_payments ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE line_items    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_fund_payments_deleted ON fund_payments (deleted_at);
CREATE INDEX IF NOT EXISTS idx_line_items_deleted ON line_items (deleted_at);

-- Redefine analytical views to exclude soft-deleted line_items (line_items.deleted_at
-- didn't exist when 01_schema.sql's views were first created). Without this,
-- deleting a line item via the admin panel would still count it in category
-- spend, price history, uncategorized-items curation and tax reconciliation —
-- inconsistent with the dashboard/queries.py fix from the same admin-CRUD feature.
-- Redefined here (not just in 01_schema.sql) so it also reaches already-running
-- databases the next time `make fund` applies this file.
CREATE OR REPLACE VIEW v_monthly_spend_by_category AS
WITH RECURSIVE roots AS (
  SELECT id, id AS root_id, name AS root_name FROM categories WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, r.root_id, r.root_name
  FROM categories c JOIN roots r ON c.parent_id = r.id
)
SELECT date_trunc('month', COALESCE(rc.issued_date, rc.created_at::date))::date AS month,
       COALESCE(r.root_name, 'Sin categoria')    AS category,
       SUM(li.line_total)                         AS total
FROM line_items li
JOIN receipts rc ON rc.id = li.receipt_id AND rc.deleted_at IS NULL AND li.deleted_at IS NULL
LEFT JOIN roots r ON r.id = li.category_id
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;

CREATE OR REPLACE VIEW v_item_price_history AS
SELECT li.normalized_name,
       m.name AS merchant,
       rc.issued_date,
       li.unit_price
FROM line_items li
JOIN receipts rc ON rc.id = li.receipt_id AND rc.deleted_at IS NULL AND li.deleted_at IS NULL
LEFT JOIN merchants m ON m.id = rc.merchant_id
WHERE li.normalized_name IS NOT NULL
ORDER BY li.normalized_name, rc.issued_date;

CREATE OR REPLACE VIEW v_uncategorized_items AS
SELECT li.id, li.raw_text, li.normalized_name, rc.issued_date
FROM line_items li
JOIN receipts rc ON rc.id = li.receipt_id AND rc.deleted_at IS NULL AND li.deleted_at IS NULL
WHERE li.category_id IS NULL;

CREATE OR REPLACE VIEW v_tax_reconciliation AS
SELECT rc.id, rc.folio, rc.total, rc.net, rc.tax,
       COALESCE((SELECT SUM(line_total) FROM line_items li WHERE li.receipt_id = rc.id AND li.deleted_at IS NULL), 0) AS sum_lines,
       (rc.net * 1.19) AS net_times_iva
FROM receipts rc
WHERE rc.deleted_at IS NULL;
