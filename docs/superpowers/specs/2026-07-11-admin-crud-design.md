# Admin CRUD de transacciones + colección Postman

**Fecha:** 2026-07-11
**Estado:** Diseño aprobado, pendiente de plan de implementación

## Contexto y problema

Fortunia registra dinero de una sola forma: texto libre o fotos vía el bot de
Telegram (openclaw → worker `/ocr`, `/text`, `/income`). Eso está bien para los
usuarios normales (el usuario y su esposa), pero no hay forma de corregir un
error después del hecho: un monto mal transcrito, una categoría mal asignada,
un pago duplicado. El dashboard (`:8001`) es de solo lectura por diseño
(rol `fortunia_ro`), así que hoy la única forma de corregir algo es `psql`
manual.

El usuario (administrador de la app) necesita:
1. Listar todas las transacciones (boletas, ingresos, pagos del fondo común).
2. Editar valores (monto, categoría, fecha, detalle).
3. Eliminar registros incorrectos o duplicados.
4. Una colección Postman lista para usar como panel de administración ad-hoc.

## Decisiones (acordadas con el usuario)

| Tema | Decisión |
|------|----------|
| Alcance de entidades | Todo: `receipts` + `line_items`, `incomes`, `fund_payments` |
| Dónde viven los endpoints | En el **worker** (`:8002`) — ya tiene el rol dueño de la DB |
| Autenticación | Ninguna adicional (igual que el resto del worker hoy) |
| Tipo de borrado | Soft-delete en todo, con endpoint de restore |
| Campos editables | Monto, categoría, fecha y detalle |
| Filtro de listado | `?month=YYYY-MM-DD` opcional (por defecto trae todo) |

### Por qué el worker y no el dashboard

El dashboard usa deliberadamente el rol `fortunia_ro` (solo `SELECT`) — es una
garantía de seguridad explícita en el proyecto (`CLAUDE.md`: "Connects via
read-only DB role — never writes"). Meter escritura ahí rompe esa garantía.
El worker ya usa el rol dueño (`boleta`) para persistir OCR, así que los
endpoints admin van ahí como una sección nueva bajo `/admin/*`, reusando
`worker/db.py`.

### Por qué sin autenticación

Coherente con el resto del sistema: ni `/ocr`, ni `/text`, ni el `/admin` de
backups del dashboard tienen auth — el worker solo escucha en la red local del
Mac mini. Añadir una API key sería más protección de la que tiene cualquier
otro endpoint de escritura hoy, e introduce un secreto más que gestionar sin
un cambio real en el modelo de amenaza (mismo host, mismo usuario).

## Cambios de schema

Nueva migración `db/09_admin_soft_delete.sql` (idempotente, mismo patrón que
`06_fund.sql`/`07_fund_payments.sql`):

```sql
ALTER TABLE fund_payments ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE line_items    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
```

`receipts` e `incomes` ya tienen `deleted_at` (no se toca su schema).

**Vistas y queries que deben excluir soft-deleted:**
- `v_fund_paid` / `v_fund_monthly` (`db/07_fund_payments.sql`): agregar
  `WHERE fp.deleted_at IS NULL` al `FROM fund_payments fp`.
- `dashboard/queries.py`: cualquier query sobre `line_items` o `fund_payments`
  debe filtrar `deleted_at IS NULL`. Las que ya filtran `receipts.deleted_at IS
  NULL` / `incomes.deleted_at IS NULL` no cambian.

## Endpoints nuevos (worker, `worker/admin.py` + router en `worker/app.py`)

Prefijo común `/admin`. Todas las respuestas son JSON.

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/admin/receipts?month=` | Lista boletas (header), no soft-deleted por defecto |
| GET | `/admin/receipts/{id}/items` | Line items de una boleta |
| PATCH | `/admin/receipts/{id}` | Edita `total`, `issued_date` |
| DELETE | `/admin/receipts/{id}` | Soft-delete (`deleted_at = now()`) |
| POST | `/admin/receipts/{id}/restore` | `deleted_at = NULL` |
| PATCH | `/admin/line-items/{id}` | Edita `unit_price`, `qty`, `line_total`, `category_id` |
| DELETE | `/admin/line-items/{id}` | Soft-delete |
| POST | `/admin/line-items/{id}/restore` | Restore |
| GET | `/admin/incomes?month=` | Lista ingresos |
| PATCH | `/admin/incomes/{id}` | Edita `amount`, `category_id`, `issued_date`, `raw_text` (detalle) |
| DELETE | `/admin/incomes/{id}` | Soft-delete |
| POST | `/admin/incomes/{id}/restore` | Restore |
| GET | `/admin/fund-payments?month=` | Lista pagos del fondo común |
| PATCH | `/admin/fund-payments/{id}` | Edita `amount`, `category_id`, `month`, `detail` |
| DELETE | `/admin/fund-payments/{id}` | Soft-delete |
| POST | `/admin/fund-payments/{id}/restore` | Restore |
| GET | `/admin/categories` | Lista categorías (id + nombre + classification), para poblar el campo `category_id` al editar |

`month` se interpreta como el mes calendario completo (`issued_date`/`month`
entre el primer y el último día de ese mes).

`PATCH` solo acepta los campos listados por entidad (Pydantic model con todos
los campos opcionales) — cualquier otro campo del body se ignora, no hay
edición de columnas fuera de la lista acordada (ej. no se edita `image_sha256`
ni `ocr_raw_text`).

`DELETE`/`restore` devuelven el registro actualizado con su `deleted_at`.

## Colección Postman

Archivo `postman/fortunia-admin.postman_collection.json`, con:
- Variable de colección `base_url` = `http://localhost:8002`.
- Carpetas: **Receipts**, **Line Items**, **Incomes**, **Fund Payments**,
  **Categories** — cada una con requests List / Get sub-recurso / Update /
  Delete / Restore, usando `{{base_url}}` y placeholders `:id`/`:month` en la
  URL para que sea trivial cambiarlos en la barra de Postman.
- Nombres de requests en español, coherente con el resto del proyecto.

## Testing

- `worker/tests/test_admin.py`: cubre, por cada entidad, list (con y sin
  filtro de mes), update (campos válidos + rechazo de campos no permitidos),
  delete (queda con `deleted_at` seteado y desaparece de list), restore
  (`deleted_at` vuelve a `NULL` y reaparece en list).
- Verificar que `v_fund_monthly` deja de contar un `fund_payment` después de
  soft-delete (test de integración sobre la vista, no solo la tabla).

## Fuera de alcance

- No se edita `merchants` ni `categories` (solo lectura de categorías para
  poblar el selector).
- No hay UI web para esto — es deliberadamente solo API + Postman, para uso
  exclusivo del administrador vía herramienta técnica, no para la esposa.
- No se agrega autenticación en este trabajo (documentado arriba como
  decisión explícita, no como pendiente).
