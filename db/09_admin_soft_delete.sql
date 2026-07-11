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
