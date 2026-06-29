-- Seed Chilean retail taxonomy + categorization dictionary. Extend freely.
-- Categories are hierarchical (parent_id self-reference).

INSERT INTO categories (id, parent_id, name, classification) OVERRIDING SYSTEM VALUE VALUES
  (1,  NULL, 'Alimentos',     'expense'),
  (2,  1,    'Lacteos',       'expense'),
  (3,  1,    'Panaderia',     'expense'),
  (4,  1,    'Frutas y Verduras', 'expense'),
  (5,  1,    'Carnes',        'expense'),
  (6,  1,    'Abarrotes',     'expense'),
  (7,  NULL, 'Bebidas',       'expense'),
  (8,  7,    'Bebidas sin alcohol', 'expense'),
  (9,  7,    'Alcohol',       'expense'),
  (10, NULL, 'Aseo y Limpieza', 'expense'),
  (11, NULL, 'Cuidado Personal', 'expense'),
  (12, NULL, 'Mascotas',      'expense'),
  (13, NULL, 'Otros',         'expense')
ON CONFLICT (id) DO NOTHING;

-- keep the identity sequence past the manual ids
SELECT setval(pg_get_serial_sequence('categories','id'), (SELECT MAX(id) FROM categories));

-- Categorization rules: first match by priority wins. Patterns are UPPER, matched case-insensitively.
INSERT INTO item_aliases (pattern, match_type, normalized_name, category_id, priority) VALUES
  ('LECHE',     'prefix',   'Leche',        2,  10),
  ('LCH',       'prefix',   'Leche',        2,  10),
  ('YOGHURT',   'contains', 'Yoghurt',      2,  20),
  ('QUESO',     'contains', 'Queso',        2,  20),
  ('MANTEQUILLA','contains','Mantequilla',  2,  20),
  ('PAN',       'prefix',   'Pan',          3,  10),
  ('MARRAQUETA','contains', 'Marraqueta',   3,  10),
  ('HALLULLA',  'contains', 'Hallulla',     3,  10),
  ('PLATANO',   'contains', 'Platano',      4,  20),
  ('MANZANA',   'contains', 'Manzana',      4,  20),
  ('TOMATE',    'contains', 'Tomate',       4,  20),
  ('PALTA',     'contains', 'Palta',        4,  20),
  ('POLLO',     'contains', 'Pollo',        5,  20),
  ('CARNE',     'contains', 'Carne',        5,  20),
  ('VACUNO',    'contains', 'Vacuno',       5,  20),
  ('ARROZ',     'prefix',   'Arroz',        6,  20),
  ('FIDEO',     'contains', 'Fideos',       6,  20),
  ('ACEITE',    'contains', 'Aceite',       6,  20),
  ('AZUCAR',    'contains', 'Azucar',       6,  20),
  ('COCA COLA', 'prefix',   'Coca-Cola',    8,  10),
  ('BEBIDA',    'contains', 'Bebida',       8,  30),
  ('AGUA',      'prefix',   'Agua',         8,  30),
  ('JUGO',      'contains', 'Jugo',         8,  30),
  ('CERVEZA',   'contains', 'Cerveza',      9,  10),
  ('VINO',      'prefix',   'Vino',         9,  10),
  ('DETERGENTE','contains', 'Detergente',   10, 20),
  ('CLORO',     'contains', 'Cloro',        10, 20),
  ('CONFORT',   'contains', 'Papel higienico', 10, 20),
  ('SHAMPOO',   'contains', 'Shampoo',      11, 20),
  ('JABON',     'contains', 'Jabon',        11, 20),
  ('PASTA DENTAL','contains','Pasta dental',11, 20),
  ('WHISKAS',   'contains', 'Comida gato',  12, 10),
  ('DOG CHOW',  'contains', 'Comida perro', 12, 10)
ON CONFLICT DO NOTHING;
