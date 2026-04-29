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
    applicable_to VARCHAR(10) NOT NULL DEFAULT 'expense' CHECK (applicable_to IN ('expense', 'income', 'both')),
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
    type          VARCHAR(10) NOT NULL DEFAULT 'expense' CHECK (type IN ('expense', 'income')),
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

-- Users (maps Telegram ID to display name)
CREATE TABLE users (
    id          SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    display_name VARCHAR(50) NOT NULL,
    user_key    VARCHAR(50) UNIQUE NOT NULL,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_users_telegram ON users(telegram_id);

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
INSERT INTO categories (name, icon, color, applicable_to, keywords) VALUES
-- Ingresos
('Salario',                    'banknote',          '#10B981', 'income',
 ARRAY['salario','sueldo','remuneración','remuneracion','pago mensual']),
('Otros Ingresos',             'arrow-down-circle', '#6EE7B7', 'income',
 ARRAY['freelance','honorario','transferencia recibida','ingreso','pago recibido']),
-- Alimentación
('Comida',                     'shopping-cart',     '#E85D24', 'expense',
 ARRAY['supermercado','jumbo','lider','líder','tottus','unimarc','santa isabel','almacén','feria','minimarket']),
('Restaurantes',               'utensils',          '#F97316', 'expense',
 ARRAY['restaurant','restaurante','sushi','pizza','café','cafe','almuerzo','cena','panadería','panaderia','mcdonalds','burger','sandwichería']),
-- Servicios básicos
('Servicio Agua',              'droplets',          '#38BDF8', 'expense',
 ARRAY['agua','servicio agua','aguas andinas','esval','essbio','bill agua']),
('Servicio Energía Eléctrica', 'zap',               '#FACC15', 'expense',
 ARRAY['luz','electricidad','energía eléctrica','energia electrica','enel','cge','chilquinta']),
-- Créditos
('Crédito Hipotecario',        'building',          '#6366F1', 'expense',
 ARRAY['hipoteca','crédito hipotecario','credito hipotecario','dividendo','mortgage']),
('Crédito Consumo',            'credit-card',       '#8B5CF6', 'expense',
 ARRAY['crédito consumo','credito consumo','préstamo consumo','prestamo consumo','cuota consumo']),
('Crédito Automotriz',         'car',               '#A78BFA', 'expense',
 ARRAY['crédito auto','credito auto','crédito automotriz','credito automotriz','cuota auto','leasing']),
('TDC',                        'wallet',            '#EC4899', 'expense',
 ARRAY['tdc','tarjeta de crédito','tarjeta de credito','tarjeta credito','visa','mastercard','amex']),
-- Transporte
('Transporte',                 'car',               '#3B8BD4', 'expense',
 ARRAY['uber','didi','cabify','taxi','metro','bip','tag','peaje']),
('Estacionamiento',            'parking-square',    '#64748B', 'expense',
 ARRAY['estacionamiento','parking','parqueo']),
('Combustible',                'fuel',              '#F59E0B', 'expense',
 ARRAY['bencina','combustible','copec','shell','enex','petróleo','petroleo']),
-- Otros
('Salud',                      'heart-pulse',       '#5DCAA5', 'expense',
 ARRAY['farmacia','farmacias ahumada','cruz verde','salcobrand','remedio','medicamento','doctor','médico','medico','clínica','clinica','dental','isapre','fonasa']),
('Entretenimiento',            'film',              '#7F77DD', 'expense',
 ARRAY['netflix','spotify','disney','hbo','prime video','cine','cinemark','hoyts','concierto','teatro','steam','playstation']),
('Ropa',                       'shirt',             '#D4537E', 'expense',
 ARRAY['ropa','zapatos','zapatillas','camisa','vestido','h&m','zara','falabella','paris','ripley','hites']),
('Otros',                      'package',           '#5F5E5A', 'both',   ARRAY[]::text[]);
