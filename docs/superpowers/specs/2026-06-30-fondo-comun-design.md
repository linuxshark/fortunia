# Diseño — Fondo Común (gestión de gasto compartido del hogar)

**Fecha:** 2026-06-30
**Estado:** aprobado para planificación
**Contexto fuente:** `../estrategia_financiera_familiar.md`

## 1. Objetivo

Implementar un modelo de fondo común del hogar sobre la app Fortunia: un
presupuesto mensual de categorías compartidas (Agua, Electricidad, Internet,
Supermercado, etc.) que se **consume** a medida que cada categoría se paga, con
los pagos declarados por texto libre vía Telegram (worker `/text`) y visualizado
en el dashboard.

## 2. Decisiones de diseño (cerradas en brainstorming)

| # | Decisión | Elección |
|---|---|---|
| Q1 | Alcance | **Solo fondo total** este iteración. Sin rastreo de aportes por persona (Raúl/Victoria); el modelo proporcional queda para fase posterior. |
| Q2 | Semántica del saldo | **Presupuesto fijo que se consume.** Objetivo = suma de presupuestos de categorías compartidas. La barra parte llena y se vacía al pagar. `saldo_restante = objetivo − Σ pagado`. El presupuesto mensual es **editable mes a mes desde la web**. |
| Q3 | Modelo de categorías | **Reusar `categories`** con `classification='shared'`. |
| Q4 | Ruteo Telegram | **Mismo `/text`**, autodetecta categoría compartida; idempotente por `(category_id, month)` (reportar de nuevo reemplaza, no suma). |
| Escritura presupuesto | **Rol RW acotado solo a `fund_monthly`** para el dashboard. |

**Referencia UX (resuelta):** hazlacorta.org/calculadora-de-gastos-del-hogar.
Patrón adoptado para el editor de presupuesto: tarjetas por categoría con
**emoji + nombre + input `$` editable inline** y un **toggle "Compartido"**
(verde on/off). El portal además hace reparto **proporcional por persona**
(modo Proporcional vs 50/50) y un "Ahorro Conjunto" aparte — el reparto
proporcional NO se adopta esta iteración (Q1 = solo fondo total); sí se adopta
el patrón visual de tarjetas con input inline y toggle compartido.

## 3. Modelo de datos

### 3.1 `categories` (reuso + columna nueva)
- Sembrar subcategorías compartidas con `classification='shared'`:
  Agua, Electricidad, Internet, Supermercado, Arriendo/Dividendo, Jardín
  infantil, Auto (cuota), Restaurantes, Remesas Venezuela, GGCC, Gasolina, TAG,
  Ahorro.
- Añadir columna `target_amount NUMERIC(14,2)` (presupuesto por defecto, sembrado
  desde el doc de estrategia). Nullable para categorías no-shared.

### 3.2 `item_aliases` (reuso)
- Sembrar aliases compartidos (`luz`/`electricidad`→Electricidad, `agua`→Agua,
  `internet`/`wifi`→Internet, `super`/`supermercado`→Supermercado, `arriendo`/
  `dividendo`→Arriendo, `jardin`→Jardín, `gasolina`/`bencina`→Gasolina,
  `tag`→TAG, `remesa`→Remesas, `gastos comunes`/`ggcc`→GGCC, etc.).
- `categorize._QUERY` ya filtra por `classification`; no requiere cambios.

### 3.3 `fund_monthly` (tabla nueva — estado por categoría y mes)
```sql
CREATE TABLE IF NOT EXISTS fund_monthly (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id   BIGINT NOT NULL REFERENCES categories(id),
  month         DATE   NOT NULL,            -- primer día del mes
  budget_amount NUMERIC(14,2) NOT NULL,     -- editable mes a mes (init = target_amount)
  paid_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
  paid_at       TIMESTAMPTZ,
  source        TEXT,                        -- 'telegram' | 'manual'
  updated_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (category_id, month)
);
```
- `paid_amount > 0` ⇒ categoría "pagada" ese mes.
- Idempotencia de pago: `UPSERT ON CONFLICT (category_id, month)`.

### 3.4 Vista analítica
```sql
CREATE OR REPLACE VIEW v_fund_monthly AS
SELECT fm.month,
       c.name AS category,
       fm.budget_amount,
       fm.paid_amount,
       (fm.budget_amount - fm.paid_amount) AS remaining,
       (fm.paid_amount > 0)                AS paid
FROM fund_monthly fm
JOIN categories c ON c.id = fm.category_id
WHERE c.classification = 'shared';
```

### 3.5 Rol RW acotado
En `db/03_ro_role.sh`, además del SELECT global, otorgar al rol del dashboard:
```sql
GRANT SELECT, INSERT, UPDATE ON fund_monthly TO ${POSTGRES_RO_USER};
```
(`fund_monthly` usa IDENTITY; no requiere grant de secuencia separado.) Es el
único objeto escribible por el dashboard. Resto sigue SELECT-only.

## 4. Backend (worker)

- `categorize.categorize_shared(raw)` → resuelve categoría `classification='shared'`
  (reusa `_categorize`).
- `db.ensure_month(month)` → materializa filas de `fund_monthly` del mes desde
  `categories.target_amount` si faltan.
- `db.upsert_fund_payment(category_id, month, amount, source)` → UPSERT idempotente.
- `app.py:/text`: parsea → intenta `categorize_shared(raw)`.
  - Si **mapea a compartida** → ruta al fondo: `ensure_month` + `upsert_fund_payment`
    (`paid_amount = amount`, `paid_at = now`, `source='telegram'`). No crea
    `receipt`/`line_item` (evita doble conteo con KPIs de gasto OCR).
  - Si **no** → flujo de gasto actual (receipt + line_item), sin cambios.
  - Respuesta incluye `routed_to: 'fund' | 'expense'`, categoría, mes,
    `paid_amount`, `fund_remaining`.

## 5. Dashboard (UI)

- `queries.fund_status(month)` → filas de `v_fund_monthly` del mes.
- `queries.fund_totals(month)` → objetivo, pagado, restante, pct.
- `writes.set_budget(category_id, month, amount)` → módulo de escritura nuevo
  (conexión RW acotada) que hace `ensure_month` + UPDATE de `budget_amount`.
- Ruta `POST /fund/budget` (HTMX) → set_budget → devuelve el partial refrescado.
- Partial `_fund.html` (estética inspirada en hazlacorta.org/calculadora):
  - **Barra de progreso** del fondo (restante/objetivo; se vacía al pagar).
  - Tarjetas por categoría compartida: **emoji + nombre + input `$` editable
    inline** del presupuesto (POST HTMX), badge "pagado/pendiente", monto pagado.
  - Toggle "Compartido" opcional por categoría (visual; activa/desactiva su
    inclusión en el objetivo del mes).
- **Req #1** (barras de ingreso por fuente): `income_by_category` +
  `_income_bar.html` ya existen; se verifica/ajusta que muestren total
  acumulado por fuente.
- **Req #3** (reconciliación): al reportar pago por Telegram, refresco HTMX deja
  la fila en "pagado" y baja la barra.

## 6. Arquitectura y aislamiento

- Dominio del fondo (`fund_monthly`, vista, escrituras) aislado del flujo OCR de
  boletas (`receipts`/`line_items`). Comparten solo `categories`.
- El worker sigue siendo dueño de la lógica de parseo/categorización; el
  dashboard solo lee + la única escritura acotada a `fund_monthly`.

## 7. Plan por fases (workflow del usuario)

Cada fase: (1) implementación → (2) unit tests → (3) `make deploy` (Docker
Compose vía Makefile) → (4) E2E Playwright.

- **Fase A — Esquema y semilla:** `categories.target_amount`, semillas shared,
  aliases, `fund_monthly`, vista, grant RW. Tests: migración idempotente.
- **Fase B — Worker / ruteo de pago:** `categorize_shared`, `upsert_fund_payment`,
  `ensure_month`, `/text` ramifica. Tests: unit de ruteo + idempotencia.
- **Fase C — Dashboard lectura:** `fund_status`, `fund_totals`, `_fund.html`,
  barra de progreso. Tests: queries + render.
- **Fase D — Edición de presupuesto:** módulo writes, `POST /fund/budget`, input
  inline. Tests: escritura acotada + permiso.
- **Fase E — E2E Playwright:** declarar pago por Telegram → categoría "pagada" +
  fondo baja; editar presupuesto mes a mes; barras de ingreso por fuente.

## 8. Criterios de aceptación

1. Barras de ingreso por fuente con total acumulado por categoría (Req #1).
2. Barra de progreso del fondo que se vacía al declarar pagos (Req #2).
3. Pago por Telegram categoriza, marca "pagado" el mes y descuenta del fondo;
   idempotente por (categoría, mes) (Req #2/#3).
4. Lista de categorías compartidas que pasan a "pagado" visualmente (Req #3).
5. Presupuesto mensual editable desde la web (Q2), escritura acotada a
   `fund_monthly`.
