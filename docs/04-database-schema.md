# 04 — Postgres Schema

Design principle from the reference apps (Firefly III / Actual Budget / Maybe Finance): all three converge on a **header/detail split**, but **none model individual line items** — they stop at transaction level. This design **extends** them with a dedicated `line_items` table.

Rules borrowed:
- **Money as `NUMERIC`, never float** (lesson from all three). CLP has no decimals, but `NUMERIC(14,2)` stays general and `SUM`-exact.
- **Dedup** receipts on `(rut_emisor, folio, doc_type)` (SII-guaranteed identity) **+** `image_sha256` (same photo never ingested twice).
- **Provenance tracking** (`ted` vs `ocr` vs `xml`) for auditability — which field came from the trustworthy barcode vs OCR.
- **Categorization without an LLM** via a rules/dictionary engine (Maybe/Firefly pattern), matched at ingest with `ILIKE`/regex.
- **Skip Firefly's double-entry** (two transaction legs per line) — no account ledger in receipt scanning, only adds joins.

## DDL

```sql
-- Merchants: dedup on RUT (natural key in Chile), fallback normalized_name
CREATE TABLE merchants (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  rut             TEXT UNIQUE,                 -- nullable; SII RUT emisor
  name            TEXT NOT NULL,
  normalized_name TEXT,
  giro            TEXT,                        -- SII business activity
  address         TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON merchants (lower(normalized_name));

-- Hierarchical categories (Maybe pattern: Alimentos > Lacteos > Leche)
CREATE TABLE categories (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id      BIGINT REFERENCES categories(id),
  name           TEXT NOT NULL,
  classification TEXT DEFAULT 'expense',
  color          TEXT
);

-- Receipts (header): full SII DTE header
CREATE TABLE receipts (
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
  total             NUMERIC(14,2) NOT NULL,    -- MntTotal
  ted_total         NUMERIC(14,2),             -- MNT from barcode (ground truth)
  currency          CHAR(3) DEFAULT 'CLP',
  header_source     TEXT DEFAULT 'ocr',        -- 'ted' | 'ocr' | 'xml'
  validation_status TEXT DEFAULT 'pending',    -- 'ok' | 'review' | 'failed'
  source_image_path TEXT,
  image_sha256      TEXT UNIQUE,               -- idempotency key
  ocr_engine        TEXT,                      -- 'apple_vision' | 'paddle' | 'tesseract'
  ocr_raw_text      TEXT,
  ocr_confidence    REAL,
  created_at        TIMESTAMPTZ DEFAULT now(),
  deleted_at        TIMESTAMPTZ,               -- soft delete
  UNIQUE (rut_emisor, folio, doc_type)         -- SII invoice identity
);

-- Line items (the table none of the reference apps have)
CREATE TABLE line_items (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  receipt_id      BIGINT NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  line_no         INT,
  raw_text        TEXT,                        -- exact OCR string, for re-parsing
  normalized_name TEXT,                        -- dictionary-mapped
  category_id     BIGINT REFERENCES categories(id),
  category_source TEXT,                        -- 'rule' | 'manual' | 'unmatched'
  qty             NUMERIC(10,3) DEFAULT 1,
  unit_price      NUMERIC(14,2),
  line_total      NUMERIC(14,2),
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Deterministic, no-LLM categorization dictionary
CREATE TABLE item_aliases (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pattern         TEXT NOT NULL,
  match_type      TEXT NOT NULL,               -- 'exact'|'prefix'|'contains'|'regex'
  normalized_name TEXT,
  category_id     BIGINT REFERENCES categories(id),
  priority        INT DEFAULT 100
);
```

## Dedup & idempotent ingest

```sql
-- 1) receipt: skip if same photo already ingested
INSERT INTO receipts (image_sha256, ...) VALUES ($1, ...)
ON CONFLICT (image_sha256) DO NOTHING
RETURNING id;
-- if no row returned, receipt already exists -> do not insert line_items
```

- Primary dedup: `image_sha256` (same photo).
- Secondary identity: `UNIQUE (rut_emisor, folio, doc_type)` — the SII invoice identity (handles the same receipt re-photographed).
- Fuzzy fallback when OCR can't read the folio: `(merchant_id, issued_date, total)`.

## Categorization (deterministic, at ingest)

```sql
-- first match by priority wins; contains via ILIKE, regex via ~*
SELECT category_id, normalized_name
FROM item_aliases
WHERE (match_type='contains' AND $1 ILIKE '%'||pattern||'%')
   OR (match_type='prefix'   AND $1 ILIKE pattern||'%')
   OR (match_type='exact'    AND $1 ILIKE pattern)
   OR (match_type='regex'    AND $1 ~* pattern)
ORDER BY priority
LIMIT 1;
```

Seed Chilean retail abbreviations: `LECHE%`/`LCH%` → Lácteos, `COCA COLA%` → Bebidas, `PAN%` → Panadería, etc. Cold-start is weak until seeded; `v_uncategorized_items` drives curation.

## Analytical views

| View | Purpose |
|------|---------|
| `v_monthly_spend_by_category` | `SUM(line_total)` grouped by `date_trunc('month', issued_date)` × category, with **recursive CTE rollup** on `categories.parent_id` |
| `v_spend_by_merchant` | total spend per merchant over time |
| `v_item_price_history` | `normalized_name × merchant × issued_date × unit_price` — track per-product inflation |
| `v_uncategorized_items` | `WHERE category_id IS NULL` — review/curation queue |
| `v_tax_reconciliation` | flags rows where `SUM(line_total) ≉ total` or `net*1.19 ≉ total` (OCR-error detector) |

## Schema rationale (per reference app)

- **Actual Budget** → integer-money lesson, `imported_id`-style dedup hook (we use `image_sha256`), self-referential split idea.
- **Maybe Finance** → cleanest header/detail separation, dedicated `merchants` table, hierarchical categories, and the **rules/conditions/actions** engine (basis for `item_aliases`), plus a `data_enrichments`-style provenance column (`header_source`, `category_source`).
- **Firefly III** → first-class currency, trigger/action rules. Double-entry dropped.
