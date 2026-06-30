-- db/06_fund.sql — Fondo Común (gasto compartido del hogar).
-- Idempotente: seguro de re-ejecutar. Ver docs/superpowers/specs/2026-06-30-fondo-comun-design.md

-- 1) Presupuesto objetivo por categoría (default mensual; override por mes en fund_monthly)
ALTER TABLE categories ADD COLUMN IF NOT EXISTS target_amount NUMERIC(14,2);

-- 2) Categorías compartidas (classification='shared'). Montos = doc de estrategia.
-- WHERE NOT EXISTS evita duplicados (categories no tiene UNIQUE en name+classification).
INSERT INTO categories (name, classification, target_amount)
SELECT v.name, v.classification, v.amount FROM (VALUES
  ('Agua',               'shared',  30000::NUMERIC(14,2)),
  ('Electricidad',       'shared',  55000),
  ('Internet',           'shared',  30000),
  ('Supermercado',       'shared', 600000),
  ('Arriendo/Dividendo', 'shared', 800000),
  ('Jardín infantil',    'shared', 450000),
  ('Auto (cuota)',       'shared', 472000),
  ('Restaurantes',       'shared', 250000),
  ('Remesas Venezuela',  'shared', 350000),
  ('GGCC',               'shared', 100000),
  ('Gasolina',           'shared', 100000),
  ('TAG',                'shared',  80000),
  ('Ahorro',             'shared', 500000)
) AS v(name, classification, amount)
WHERE NOT EXISTS (
  SELECT 1 FROM categories WHERE name = v.name AND classification = v.classification
);

-- 3) Aliases shared (ILIKE contains). categorize._QUERY ya filtra por classification.
-- WHERE NOT EXISTS evita duplicados (item_aliases no tiene UNIQUE en pattern).
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority)
SELECT v.pattern, v.match_type, v.normalized_name,
       (SELECT id FROM categories WHERE name = v.cat_name AND classification = 'shared'),
       v.priority
FROM (VALUES
  ('agua',          'contains', 'Agua',               'Agua',               10),
  ('luz',           'contains', 'Electricidad',       'Electricidad',       10),
  ('electricidad',  'contains', 'Electricidad',       'Electricidad',       10),
  ('internet',      'contains', 'Internet',           'Internet',           10),
  ('wifi',          'contains', 'Internet',           'Internet',           10),
  ('supermercado',  'contains', 'Supermercado',       'Supermercado',       10),
  ('super',         'contains', 'Supermercado',       'Supermercado',       20),
  ('arriendo',      'contains', 'Arriendo/Dividendo', 'Arriendo/Dividendo', 10),
  ('dividendo',     'contains', 'Arriendo/Dividendo', 'Arriendo/Dividendo', 10),
  ('jardin',        'contains', 'Jardín infantil',    'Jardín infantil',    10),
  ('jardín',        'contains', 'Jardín infantil',    'Jardín infantil',    10),
  ('restaurant',    'contains', 'Restaurantes',       'Restaurantes',       10),
  ('restoran',      'contains', 'Restaurantes',       'Restaurantes',       10),
  ('remesa',        'contains', 'Remesas Venezuela',  'Remesas Venezuela',  10),
  ('venezuela',     'contains', 'Remesas Venezuela',  'Remesas Venezuela',  10),
  ('ggcc',          'contains', 'GGCC',               'GGCC',               10),
  ('gastos comunes','contains', 'GGCC',               'GGCC',               10),
  ('gasolina',      'contains', 'Gasolina',           'Gasolina',           10),
  ('bencina',       'contains', 'Gasolina',           'Gasolina',           10),
  ('combustible',   'contains', 'Gasolina',           'Gasolina',           10),
  ('tag',           'contains', 'TAG',                'TAG',                10),
  ('ahorro',        'contains', 'Ahorro',             'Ahorro',             10),
  ('cuota auto',    'contains', 'Auto (cuota)',       'Auto (cuota)',       10),
  ('cuota del auto','contains', 'Auto (cuota)',       'Auto (cuota)',       10)
) AS v(pattern, match_type, normalized_name, cat_name, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM item_aliases WHERE pattern = v.pattern
    AND category_id = (SELECT id FROM categories WHERE name = v.cat_name AND classification = 'shared')
);

-- 4) Estado por categoría y mes (presupuesto editable + pago)
CREATE TABLE IF NOT EXISTS fund_monthly (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id   BIGINT NOT NULL REFERENCES categories(id),
  month         DATE   NOT NULL,                  -- primer día del mes
  budget_amount NUMERIC(14,2) NOT NULL,
  paid_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
  paid_at       TIMESTAMPTZ,
  source        TEXT,                              -- 'telegram' | 'manual'
  updated_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (category_id, month)
);
CREATE INDEX IF NOT EXISTS idx_fund_monthly_month ON fund_monthly (month);

-- 5) Vista analítica del fondo
CREATE OR REPLACE VIEW v_fund_monthly AS
SELECT fm.month,
       c.name                               AS category,
       fm.budget_amount,
       fm.paid_amount,
       (fm.budget_amount - fm.paid_amount)  AS remaining,
       (fm.paid_amount > 0)                 AS paid
FROM fund_monthly fm
JOIN categories c ON c.id = fm.category_id
WHERE c.classification = 'shared';
