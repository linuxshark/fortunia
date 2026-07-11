-- Token-free boleta scanner — schema. See docs/04-database-schema.md.
-- Money as NUMERIC (never float). Dedup on image_sha256 + (rut_emisor, folio, doc_type).

-- Merchants: dedup on RUT (natural key in Chile), fallback normalized_name
CREATE TABLE IF NOT EXISTS merchants (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  rut             TEXT UNIQUE,                 -- nullable; SII RUT emisor
  name            TEXT NOT NULL,
  normalized_name TEXT,
  giro            TEXT,                        -- SII business activity
  address         TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_merchants_norm ON merchants (lower(normalized_name));

-- Hierarchical categories (Alimentos > Lacteos > Leche)
CREATE TABLE IF NOT EXISTS categories (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id      BIGINT REFERENCES categories(id),
  name           TEXT NOT NULL,
  classification TEXT DEFAULT 'expense',
  color          TEXT
);

-- Receipts (header): full SII DTE header
CREATE TABLE IF NOT EXISTS receipts (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  merchant_id       BIGINT REFERENCES merchants(id),
  doc_type          TEXT,                      -- 'boleta' | 'factura'
  tipo_dte          SMALLINT,                  -- 39/41/33/34
  folio             TEXT,
  rut_emisor        TEXT,
  rut_receptor      TEXT,
  issued_date       DATE,
  net               NUMERIC(14,2),             -- MntNeto
  tax               NUMERIC(14,2),             -- IVA
  tax_rate          NUMERIC(5,2) DEFAULT 19.0,
  exento            NUMERIC(14,2),
  total             NUMERIC(14,2),             -- MntTotal (nullable until extracted)
  ted_total         NUMERIC(14,2),             -- MNT from barcode (ground truth)
  currency          CHAR(3) DEFAULT 'CLP',
  header_source     TEXT DEFAULT 'ocr',        -- 'ted' | 'ocr' | 'xml'
  validation_status TEXT DEFAULT 'pending',    -- 'ok' | 'review' | 'failed' | 'pending'
  source_image_path TEXT,
  image_sha256      TEXT UNIQUE,               -- idempotency key
  ocr_engine        TEXT,                      -- 'apple_vision' | 'paddle' | 'tesseract'
  ocr_raw_text      TEXT,
  ocr_confidence    REAL,
  created_at        TIMESTAMPTZ DEFAULT now(),
  deleted_at        TIMESTAMPTZ,
  UNIQUE (rut_emisor, folio, doc_type)         -- SII invoice identity
);

-- Line items (the table none of the reference apps have)
CREATE TABLE IF NOT EXISTS line_items (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  receipt_id      BIGINT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  line_no         INT,
  raw_text        TEXT,
  normalized_name TEXT,
  category_id     BIGINT REFERENCES categories(id),
  category_source TEXT,                        -- 'rule' | 'manual' | 'unmatched'
  qty             NUMERIC(10,3) DEFAULT 1,
  unit_price      NUMERIC(14,2),
  line_total      NUMERIC(14,2),
  created_at      TIMESTAMPTZ DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_line_items_receipt ON line_items (receipt_id);

-- Deterministic, no-LLM categorization dictionary
CREATE TABLE IF NOT EXISTS item_aliases (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pattern         TEXT NOT NULL,
  match_type      TEXT NOT NULL,               -- 'exact'|'prefix'|'contains'|'regex'
  normalized_name TEXT,
  category_id     BIGINT REFERENCES categories(id),
  priority        INT DEFAULT 100
);

-- ---------- Analytical views ----------

-- Monthly spend by category, rolled up to top-level parent via recursive CTE
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

CREATE OR REPLACE VIEW v_spend_by_merchant AS
SELECT m.name AS merchant,
       date_trunc('month', COALESCE(rc.issued_date, rc.created_at::date))::date AS month,
       SUM(rc.total) AS total
FROM receipts rc
LEFT JOIN merchants m ON m.id = rc.merchant_id
WHERE rc.deleted_at IS NULL
GROUP BY 1, 2
ORDER BY 2 DESC, 3 DESC;

-- Per-product price history (track inflation)
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

-- Uncategorized items (drives dictionary curation)
CREATE OR REPLACE VIEW v_uncategorized_items AS
SELECT li.id, li.raw_text, li.normalized_name, rc.issued_date
FROM line_items li
JOIN receipts rc ON rc.id = li.receipt_id AND rc.deleted_at IS NULL AND li.deleted_at IS NULL
WHERE li.category_id IS NULL;

-- Tax reconciliation (OCR-error detector)
CREATE OR REPLACE VIEW v_tax_reconciliation AS
SELECT rc.id, rc.folio, rc.total, rc.net, rc.tax,
       COALESCE((SELECT SUM(line_total) FROM line_items li WHERE li.receipt_id = rc.id AND li.deleted_at IS NULL), 0) AS sum_lines,
       (rc.net * 1.19) AS net_times_iva
FROM receipts rc
WHERE rc.deleted_at IS NULL;
