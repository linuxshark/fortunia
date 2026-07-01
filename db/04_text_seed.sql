-- Taxonomía + reglas para gastos por texto libre ("gaste 40.000 en bencina").
-- Extiende 02_seed.sql con categorías que no aparecen en boletas de super pero
-- sí en gastos del día a día (transporte, servicios, salud…). Idempotente:
-- se monta en initdb (instalación nueva) y se aplica a mano en la DB viva.

INSERT INTO categories (id, parent_id, name, classification) OVERRIDING SYSTEM VALUE VALUES
  (14, NULL, 'Transporte',          'expense'),
  (15, 14,   'Combustible',         'expense'),
  (16, 14,   'Transporte publico',  'expense'),
  (17, NULL, 'Salud',               'expense'),
  (18, NULL, 'Servicios',           'expense'),   -- luz, agua, gas, internet
  (19, NULL, 'Restaurant',          'expense'),   -- comida fuera de casa
  (20, NULL, 'Entretenimiento',     'expense'),
  (21, NULL, 'Hogar',               'expense'),
  (22, NULL, 'Educacion',           'expense')
ON CONFLICT (id) DO NOTHING;

-- mantener la secuencia de identidad por delante de los ids manuales
SELECT setval(pg_get_serial_sequence('categories','id'), (SELECT MAX(id) FROM categories));

-- Reglas de categorización (idempotentes: sólo inserta patrones que faltan).
-- item_aliases no tiene índice único, así que guardamos con NOT EXISTS.
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority)
SELECT v.pattern, v.match_type, v.normalized_name, v.category_id, v.priority
FROM (VALUES
  ('BENCINA',     'contains', 'Bencina',           15, 10),
  ('COMBUSTIBLE', 'contains', 'Combustible',       15, 10),
  ('GASOLINA',    'contains', 'Bencina',           15, 10),
  ('PETROLEO',    'contains', 'Petroleo',          15, 10),
  ('DIESEL',      'contains', 'Diesel',            15, 10),
  ('COPEC',       'contains', 'Bencina',           15, 15),
  ('SHELL',       'contains', 'Bencina',           15, 15),
  ('METRO',       'contains', 'Metro',             16, 10),
  ('MICRO',       'contains', 'Micro',             16, 10),
  ('PASAJE',      'contains', 'Pasaje',            16, 10),
  ('UBER',        'contains', 'Uber',              16, 10),
  ('TAXI',        'contains', 'Taxi',              16, 10),
  ('CABIFY',      'contains', 'Cabify',            16, 10),
  ('DIDI',        'contains', 'Didi',              16, 10),
  ('BIP',         'contains', 'Tarjeta Bip',       16, 15),
  ('ALMUERZO',    'contains', 'Almuerzo',          19, 10),
  ('ONCE',        'contains', 'Once',              19, 20),
  ('RESTAURANT',  'contains', 'Restaurant',        19, 10),
  ('COMIDA',      'contains', 'Comida',            19, 30),
  ('CAFE',        'contains', 'Cafe',              19, 20),
  ('FARMACIA',    'contains', 'Farmacia',          17, 10),
  ('REMEDIO',     'contains', 'Remedio',           17, 10),
  ('MEDICO',      'contains', 'Medico',            17, 10),
  ('DOCTOR',      'contains', 'Doctor',            17, 10),
  ('CONSULTA',    'contains', 'Consulta medica',   17, 20),
  ('LUZ',         'contains', 'Electricidad',      18, 20),
  ('ELECTRICIDAD','contains', 'Electricidad',      18, 10),
  ('AGUA POTABLE','contains', 'Agua potable',      18, 10),
  ('INTERNET',    'contains', 'Internet',          18, 10),
  ('CUENTA',      'contains', 'Cuenta de servicio',18, 30),
  ('CINE',        'contains', 'Cine',              20, 10),
  ('NETFLIX',     'contains', 'Netflix',           20, 10),
  ('SPOTIFY',     'contains', 'Spotify',           20, 10),
  ('SUPERMERCADO','contains', 'Supermercado',       1, 30)
) AS v(pattern, match_type, normalized_name, category_id, priority)
WHERE NOT EXISTS (
  SELECT 1 FROM item_aliases ia WHERE ia.pattern = v.pattern
);
