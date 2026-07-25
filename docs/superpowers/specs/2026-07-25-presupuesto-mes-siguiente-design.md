# Presupuesto del mes siguiente — panel volteado del Fondo Común

Fecha: 2026-07-25
Estado: aprobado, pendiente de implementación

## Problema

El bloque "Fondo Común del hogar" de la portada permite editar el presupuesto de
cada categoría compartida, pero solo del mes que se está viendo. No hay forma de
planificar el mes siguiente:

- El selector de mes (`queries.months_available()`) lista únicamente meses que
  tienen boletas, así que un mes futuro nunca es navegable.
- Cuando un mes no tiene fila en `fund_monthly`, `queries.fund_status()` cae en
  `categories.target_amount` (los montos sembrados por `db/06_fund.sql`). Esa
  caída al default es lo que da la impresión de que el presupuesto está "fijo en
  la base de datos".

El modelo de datos ya es por mes: `fund_monthly` tiene `UNIQUE (category_id, month)`
y `writes.set_budget()` hace UPSERT sobre ese par. Lo que falta es la interfaz de
planificación, no el esquema.

## Solución

Un botón en el header del Fondo Común voltea el bloque completo en 3D y muestra,
en el reverso, la misma grilla de tarjetas pero para el **mes siguiente** al que
se está viendo. Al abrir el panel se siembran las filas del mes destino copiando
los montos vigentes del mes origen; cada campo guarda al cambiarlo, igual que en
el frente.

## Decisiones de diseño

| Decisión | Elegido | Descartado |
|---|---|---|
| Mes que se planifica | Siempre `mes_visible + 1` | Selector de mes propio; editar defaults globales |
| Pre-llenado | Copia del **presupuesto** vigente del mes origen | Copia del pagado real; defaults; vacío |
| Persistencia | Siembra completa al abrir + guardado por campo | Guardado por campo sin siembra; botón "Guardar" global |
| Alcance del volteo | Bloque completo, header incluido | Solo la grilla; flip por tarjeta |
| Contenido del reverso | Input + delta por tarjeta, total en vivo en el header | Solo input; comparación de totales en el header |
| Navegación posterior | El mes presupuestado entra al selector | Solo accesible por el flip; mes siguiente siempre presente |

## Esquema de base de datos

Sin cambios. `fund_monthly` y `categories.target_amount` cubren el caso. El rol
`fortunia_ro` ya tiene `GRANT SELECT, INSERT, UPDATE ON fund_monthly`
(`db/03_ro_role.sh`), que es todo lo que la siembra necesita; el `id` es una
columna identidad y no requiere permisos extra sobre su secuencia.

## Componentes

### `dashboard/queries.py`

**`next_month(month: str) -> str`**
`'YYYY-MM'` → mes siguiente en el mismo formato. Función pura, sin DB. Maneja el
salto de diciembre a enero (`'2026-12'` → `'2027-01'`).

**`fund_plan(month: str, compare_to: str) -> dict`**
Estado de planificación de `month`, comparado contra `compare_to`. Devuelve
`{"month": str, "rows": [...], "total": float}` donde cada fila lleva:

- `category_id`, `category`
- `budget_amount` — presupuesto efectivo de `month`
  (`COALESCE(fm.budget_amount, c.target_amount, 0)`)
- `prev_budget` — presupuesto efectivo de `compare_to`, misma expresión
- `delta` — `budget_amount - prev_budget`

Solo categorías con `classification = 'shared'`, ordenadas por `c.id` para que la
grilla del reverso coincida visualmente con la del frente. `total` es la suma de
`budget_amount`.

**`months_available()`** — se amplía con un `UNION` de los meses distintos
presentes en `fund_monthly` (`to_char(month, 'YYYY-MM')`), manteniendo el
`ORDER BY m DESC`. Así un mes recién presupuestado aparece en el selector aunque
todavía no tenga boletas.

**`fund_delta_label(delta: float) -> tuple[str, str]`**
Función pura: dado el delta devuelve `(texto, clase_css)`.

- `delta > 0` → `("+$50.000 ▲", "is-up")`
- `delta < 0` → `("−$20.000 ▼", "is-down")`
- `delta == 0` → `("= sin cambios", "is-same")`

El formato del monto reutiliza el mismo criterio del filtro `clp` (separador de
miles con punto, sin decimales).

### `dashboard/writes.py`

**`seed_month_from(src: str, dst: str) -> None`**
Copia los presupuestos efectivos de `src` a `dst` para todas las categorías
compartidas, en una sola sentencia:

```sql
INSERT INTO fund_monthly (category_id, month, budget_amount, paid_amount, source)
SELECT c.id,
       %(dst)s::date,
       COALESCE(fm.budget_amount, c.target_amount, 0),
       0,
       'manual'
FROM categories c
LEFT JOIN fund_monthly fm
  ON fm.category_id = c.id AND fm.month = %(src)s::date
WHERE c.classification = 'shared'
ON CONFLICT (category_id, month) DO NOTHING
```

`ON CONFLICT DO NOTHING` hace la operación idempotente: si el mes destino ya tiene
filas, sus montos —incluidos los ya editados a mano— quedan intactos, y solo se
crean las categorías que faltaban. Reabrir el panel es seguro.

Ambos argumentos son `'YYYY-MM'`; la función los convierte a primer día del mes,
igual que `set_budget()`.

### `dashboard/app.py`

**`POST /fund/plan`** — recibe `month` (el mes visible) por formulario. Calcula
`target = q.next_month(month)`, llama a `writes.seed_month_from(month, target)` y
renderiza `_fund_plan.html` con `q.fund_plan(target, compare_to=month)`. Es POST
porque escribe.

**`POST /fund/budget`** — se le agregan dos campos opcionales,
`view: str = Form("")` y `compare_to: str = Form("")`. Si `view` vale `"plan"`,
tras guardar re-renderiza `_fund_plan.html` con
`q.fund_plan(month, compare_to=compare_to)`, de modo que el total del header y los
deltas se actualicen en vivo. Con cualquier otro valor mantiene el comportamiento
actual de devolver `_overview.html`. El frente no cambia.

`compare_to` viaja como campo oculto en cada formulario del reverso, así no hace
falta un helper `prev_month()`: el mes origen ya se conoce al renderizar el panel.

### `dashboard/templates/`

**`_fund.html`** — el `<article class="fund">` actual pasa a ser la cara frontal
dentro de un contenedor de volteo:

```
<div class="fund-flip">          <!-- display: grid -->
  <div class="fund-face fund-front">  ... contenido actual ... </div>
  <div class="fund-face fund-back" id="fund-back"></div>
</div>
```

Ambas caras ocupan la misma celda de grid (`grid-area: 1 / 1`), de modo que el
alto del contenedor lo determina la cara más alta y no hay saltos de layout ni
posicionamiento absoluto.

En el header del frente, junto a "Objetivo", un botón:

```
<button class="fund-flip-btn" hx-post="/fund/plan" hx-target="#fund-back"
        hx-swap="innerHTML" hx-vals='{"month": "{{ month }}"}'
        hx-on::after-swap="this.closest('.fund-flip').classList.add('is-flipped')">
```

Se usa `after-swap` y no `after-request` a propósito: solo se dispara cuando el
contenido llegó y se insertó, así nunca se ve girar una cara vacía, y un error del
servidor (que no produce swap) deja la card sin voltear.

**`_fund_plan.html`** (nuevo) — la cara trasera:

- Header: `Presupuesto de <Mes> <Año>` (nombre del mes en español) y el total
  objetivo del mes, con la clase `clp`. Botón "Volver" que solo quita la clase
  `is-flipped` del contenedor, sin request.
- Grilla con la misma estructura de tarjeta que el frente: emoji, nombre, input
  de monto (`hx-post="/fund/budget"`, `hx-trigger="change"`, `hx-target="#fund-back"`,
  con los ocultos `month`, `category_id`, `view=plan` y `compare_to`).
- Bajo el input, el delta contra el mes origen según `fund_delta_label`.
- Sin barra de progreso ni badge de estado: en un mes futuro no hay pagos.

**`static/` CSS** — `.fund-flip` es el elemento que rota:
`transform: perspective(1600px) rotateY(0)`, `transform-style: preserve-3d`, y
`.is-flipped` lo lleva a `rotateY(180deg)`. La perspectiva va en la propia función
`transform` para no necesitar un wrapper extra. Las dos caras comparten celda
(`grid-area: 1 / 1`) y llevan `backface-visibility: hidden`; la trasera nace ya
rotada en `rotateY(180deg)`, de modo que queda legible cuando el conjunto gira.
Transición de 450 ms con easing suave.
Dentro de `@media (prefers-reduced-motion: reduce)` el volteo se sustituye por un
cross-fade de opacidad de 150 ms.

Los colores del delta reutilizan las variables ya definidas para los estados de
tarjeta (ámbar de "parcial" para subidas, verde de "pagado" para bajadas, gris
apagado para "sin cambios"), para no introducir una paleta nueva.

## Flujo

```
Portada (Julio)
  └─ click en "Planificar Agosto"
       └─ POST /fund/plan {month: 2026-07}
            ├─ seed_month_from('2026-07', '2026-08')   -- idempotente
            └─ render _fund_plan.html  →  #fund-back
                 └─ after-request: .fund-flip gana .is-flipped  →  volteo 3D
                      └─ editar un input
                           └─ POST /fund/budget {view: plan}
                                ├─ set_budget(cat, 2026-08, monto)
                                └─ re-render _fund_plan.html  (total y deltas al día)
```

## Manejo de errores

- `amount` negativo se recorta a 0, como ya hace `POST /fund/budget`.
- Un `month` malformado en `/fund/plan` hace fallar `next_month()`; la ruta valida
  el formato `YYYY-MM` y responde 400 antes de tocar la base.
- Si la siembra falla por permisos o conexión, la excepción sube y HTMX no aplica
  la clase `is-flipped` (el `hx-on::after-request` solo corre en respuestas 2xx),
  así que la card no se voltea hacia un panel vacío.

## Testing

Junto a `dashboard/tests/test_fund_card_state.py`:

- `next_month()` — mes normal, salto Dic→Ene, año bisiesto irrelevante pero
  incluido como caso de borde de formato.
- `fund_delta_label()` — positivo, negativo, cero, y el formato de miles.

Test de integración para `seed_month_from()`, verificando la idempotencia: sembrar
Agosto desde Julio, editar una categoría a un monto distinto, volver a sembrar, y
comprobar que la edición sobrevive y que no se duplicaron filas.

## Fuera de alcance

- Planificar más de un mes hacia adelante en un mismo panel.
- Editar los defaults globales `categories.target_amount` desde la web.
- Copiar el mes basándose en el gasto real en vez del presupuesto.
- Cualquier cambio al frente de la tarjeta o al cálculo de `fund_totals`.
