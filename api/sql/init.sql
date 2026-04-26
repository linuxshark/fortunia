-- Fortunia Database Schema
-- PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Categories table
CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE NOT NULL,
    icon        VARCHAR(20),
    color       VARCHAR(7),
    parent_id   INT REFERENCES categories(id) ON DELETE SET NULL,
    keywords    TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Merchants table
CREATE TABLE merchants (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) UNIQUE NOT NULL,
    normalized  VARCHAR(100) NOT NULL,
    category_id INT REFERENCES categories(id) ON DELETE SET NULL,
    rut         VARCHAR(15),
    aliases     TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_merchants_norm ON merchants USING gin(normalized gin_trgm_ops);

-- Raw messages audit trail
CREATE TABLE raw_messages (
    id           BIGSERIAL PRIMARY KEY,
    user_id      VARCHAR(50) NOT NULL,
    telegram_id  BIGINT,
    type         VARCHAR(10) NOT NULL CHECK (type IN ('text','image','audio')),
    content      TEXT,
    transcript   TEXT,
    received_at  TIMESTAMPTZ DEFAULT NOW(),
    intent       VARCHAR(20),
    intent_conf  NUMERIC(3,2),
    used_llm     BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, telegram_id)
);
CREATE INDEX idx_raw_messages_user ON raw_messages(user_id);
CREATE INDEX idx_raw_messages_intent ON raw_messages(intent);

-- Attachments (images, audio files)
CREATE TABLE attachments (
    id           BIGSERIAL PRIMARY KEY,
    user_id      VARCHAR(50),
    filename     VARCHAR(255),
    mime_type    VARCHAR(50),
    size_bytes   INT,
    sha256       CHAR(64) UNIQUE,
    storage_path TEXT,
    ocr_text     TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Expenses (main facts table)
CREATE TABLE expenses (
    id            BIGSERIAL PRIMARY KEY,
    user_id       VARCHAR(50) NOT NULL,
    amount        NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    currency      CHAR(3) NOT NULL DEFAULT 'CLP',
    category_id   INT REFERENCES categories(id) ON DELETE SET NULL,
    merchant_id   INT REFERENCES merchants(id) ON DELETE SET NULL,
    spent_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note          TEXT,
    source        VARCHAR(20) NOT NULL CHECK (source IN ('text','image','audio','manual')),
    confidence    NUMERIC(3,2),
    raw_msg_id    BIGINT REFERENCES raw_messages(id) ON DELETE SET NULL,
    attachment_id BIGINT REFERENCES attachments(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_exp_spent_at ON expenses(spent_at DESC);
CREATE INDEX idx_exp_user_month ON expenses(user_id, date_trunc('month', spent_at));
CREATE INDEX idx_exp_category ON expenses(category_id);
CREATE INDEX idx_exp_user ON expenses(user_id);

-- Intent feedback for model improvement
CREATE TABLE intent_feedback (
    id              BIGSERIAL PRIMARY KEY,
    raw_message     TEXT NOT NULL,
    classified_as   BOOLEAN NOT NULL,
    user_confirmed  BOOLEAN,
    confidence      NUMERIC(3,2),
    reason          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Materialized view for fast dashboard queries
CREATE MATERIALIZED VIEW monthly_summaries AS
SELECT
    user_id,
    date_trunc('month', spent_at) AS month,
    category_id,
    COUNT(*) AS count,
    SUM(amount) AS total,
    AVG(amount) AS avg
FROM expenses
GROUP BY user_id, date_trunc('month', spent_at), category_id;

CREATE UNIQUE INDEX ON monthly_summaries(user_id, month, category_id);

-- Seed categories with Chilean keywords
INSERT INTO categories (name, icon, color, keywords) VALUES
('Alimentación', 'utensils', '#E85D24',
 ARRAY['supermercado','super','jumbo','lider','líder','tottus','unimarc','santa isabel','almuerzo','cena','desayuno','sushi','pizza','restaurant','restaurante','café','cafe','panadería','panaderia','feria']),
('Transporte', 'car', '#3B8BD4',
 ARRAY['uber','didi','cabify','taxi','metro','bencina','combustible','peaje','tag','bip','copec','shell','enex']),
('Salud', 'heart-pulse', '#5DCAA5',
 ARRAY['farmacia','farmacias ahumada','cruz verde','salcobrand','remedio','medicamento','doctor','médico','medico','clínica','clinica','dental','isapre','fonasa']),
('Hogar', 'home', '#888780',
 ARRAY['arriendo','dividendo','luz','enel','cge','agua','aguas andinas','gas','lipigas','internet','vtr','movistar','entel','condominio','gastos comunes']),
('Entretenimiento', 'film', '#7F77DD',
 ARRAY['netflix','spotify','disney','hbo','prime video','cine','cinemark','hoyts','concierto','teatro','steam','playstation']),
('Ropa', 'shirt', '#D4537E',
 ARRAY['ropa','zapatos','zapatillas','camisa','vestido','h&m','zara','falabella','paris','ripley','hites']),
('Otros', 'package', '#5F5E5A', ARRAY[]::text[]);
