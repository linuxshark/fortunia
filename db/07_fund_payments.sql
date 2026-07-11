-- db/07_fund_payments.sql — Ledger de pagos individuales del Fondo Común.
-- Idempotente: seguro de re-ejecutar.
--
-- Problema que resuelve: fund_monthly.paid_amount era un solo número por
-- (categoría, mes) que el pago más reciente REEMPLAZABA. Sirve para boletas
-- fijas (Arriendo, Agua, Luz: pagas una vez al mes, y si te equivocas de
-- monto, corriges reenviando el monto correcto). Pero para categorías donde
-- gastas en varias transacciones sueltas durante el mes (Restaurantes,
-- Alimentos: cada comida afuera, cada compra), reemplazar pierde el registro
-- de cada transacción y descarta el detalle (ej. "KFC", "McDonald's").
--
-- Este ledger guarda CADA pago individual con su detalle. Cuánto cuenta como
-- "pagado" para el presupuesto del mes depende de categories.accumulation_mode:
--   'replace' (default) -> el pago más reciente reemplaza (boletas fijas)
--   'sum'               -> se suman todos los pagos del mes (gasto variable)

-- 1) Modo de acumulación por categoría compartida.
ALTER TABLE categories ADD COLUMN IF NOT EXISTS accumulation_mode TEXT NOT NULL DEFAULT 'replace'
  CHECK (accumulation_mode IN ('replace', 'sum'));

UPDATE categories SET accumulation_mode = 'sum'
WHERE classification = 'shared' AND name IN ('Alimentos', 'Restaurantes', 'Gasolina');

-- 2) Ledger de pagos individuales (fuente de verdad para "pagado").
CREATE TABLE IF NOT EXISTS fund_payments (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id BIGINT NOT NULL REFERENCES categories(id),
  month       DATE   NOT NULL,
  amount      NUMERIC(14,2) NOT NULL,
  detail      TEXT,
  source      TEXT,
  paid_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fund_payments_category_month ON fund_payments (category_id, month);
CREATE INDEX IF NOT EXISTS idx_fund_payments_month ON fund_payments (month);

-- 3) Cuánto está "pagado" por (categoría, mes), respetando accumulation_mode.
CREATE OR REPLACE VIEW v_fund_paid AS
SELECT fp.category_id, fp.month,
       CASE WHEN c.accumulation_mode = 'sum'
            THEN SUM(fp.amount)
            ELSE (array_agg(fp.amount ORDER BY fp.paid_at DESC, fp.id DESC))[1]
       END                    AS paid_amount,
       MAX(fp.paid_at)        AS paid_at
FROM fund_payments fp
JOIN categories c ON c.id = fp.category_id
WHERE fp.deleted_at IS NULL
GROUP BY fp.category_id, fp.month, c.accumulation_mode;

-- 4) Vista analítica del fondo (presupuesto + pagado real vía ledger).
-- DROP + CREATE (no REPLACE): el tipo de paid_amount cambia de numeric(14,2)
-- fijo (columna) a numeric derivado (SUM/array_agg), y CREATE OR REPLACE VIEW
-- no permite cambiar el tipo de una columna existente.
DROP VIEW IF EXISTS v_fund_monthly;
CREATE VIEW v_fund_monthly AS
SELECT fm.month,
       c.name                               AS category,
       fm.budget_amount,
       COALESCE(vp.paid_amount, 0)          AS paid_amount,
       (fm.budget_amount - COALESCE(vp.paid_amount, 0)) AS remaining,
       (COALESCE(vp.paid_amount, 0) > 0)    AS paid
FROM fund_monthly fm
JOIN categories c ON c.id = fm.category_id
LEFT JOIN v_fund_paid vp ON vp.category_id = fm.category_id AND vp.month = fm.month
WHERE c.classification = 'shared';
