-- db/08_ocr_fund.sql — Boletas OCR que alimentan el Fondo Común. Idempotente.
--
-- Una foto de categoría compartida (ej. supermercado → Alimentos) se guarda como
-- receipt (para el detalle de ítems) Y genera un pago del fondo VINCULADO a esa
-- boleta. Se cuenta una sola vez:
--   * la boleta ruteada al fondo lleva receipts.fund_category_id y se EXCLUYE de
--     los KPIs de gasto OCR (queries.kpis);
--   * su pago del fondo (source='ocr', receipt_id) alimenta v_fund_paid y por
--     tanto el presupuesto de la categoría compartida.
-- Así el balance mensual y el fondo reflejan el gasto sin doble conteo.

ALTER TABLE receipts      ADD COLUMN IF NOT EXISTS fund_category_id BIGINT REFERENCES categories(id);
ALTER TABLE fund_payments ADD COLUMN IF NOT EXISTS receipt_id       BIGINT REFERENCES receipts(id);

CREATE INDEX IF NOT EXISTS idx_receipts_fund_category ON receipts (fund_category_id);
CREATE INDEX IF NOT EXISTS idx_fund_payments_receipt  ON fund_payments (receipt_id);
