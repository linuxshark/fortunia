-- Income categories (classification='income', parent_id=NULL — top-level)
INSERT INTO categories (name, classification) VALUES
  ('Laboral',        'income'),
  ('Ventas',         'income'),
  ('Arriendo',       'income'),
  ('Freelance',      'income'),
  ('Otros ingresos', 'income')
ON CONFLICT DO NOTHING;

-- Income aliases: matched against the full raw income text (ILIKE, case-insensitive)
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority) VALUES
  ('sueldo',      'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('salario',     'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('bono',        'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 10),
  ('comision',    'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 20),
  ('comisión',    'contains', 'Laboral',         (SELECT id FROM categories WHERE name='Laboral'        AND classification='income'), 20),
  ('vendi',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('vendí',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('venta',       'contains', 'Ventas',          (SELECT id FROM categories WHERE name='Ventas'         AND classification='income'), 10),
  ('arriendo',    'contains', 'Arriendo',        (SELECT id FROM categories WHERE name='Arriendo'       AND classification='income'), 10),
  ('arrienda',    'contains', 'Arriendo',        (SELECT id FROM categories WHERE name='Arriendo'       AND classification='income'), 10),
  ('freelance',   'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10),
  ('consultoria', 'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10),
  ('consultoría', 'contains', 'Freelance',       (SELECT id FROM categories WHERE name='Freelance'      AND classification='income'), 10)
ON CONFLICT DO NOTHING;

-- Incomes table
CREATE TABLE IF NOT EXISTS incomes (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id BIGINT REFERENCES categories(id),
  amount      NUMERIC(14,2) NOT NULL CHECK (amount > 0),
  source_text TEXT,
  raw_text    TEXT,
  issued_date DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at  TIMESTAMPTZ DEFAULT now(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_incomes_date ON incomes (issued_date);

-- Analytical view: monthly income by category (only rows with data)
CREATE OR REPLACE VIEW v_monthly_income_by_category AS
SELECT
  date_trunc('month', issued_date)::date       AS month,
  COALESCE(c.name, 'Sin categoría')            AS category,
  SUM(i.amount)                                AS total
FROM incomes i
LEFT JOIN categories c ON c.id = i.category_id
WHERE i.deleted_at IS NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;
