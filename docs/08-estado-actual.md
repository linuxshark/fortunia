# 08 — Estado técnico actual

Documento vivo. Refleja dónde está el proyecto hoy y por qué se tomaron las decisiones que se tomaron. Actualizar tras cada sesión de trabajo significativa.

**Última actualización:** 2026-06-29

---

## Lo que funciona end-to-end

El pipeline completo está operativo en producción (Mac mini):

```
Usuario → foto de boleta en Telegram
  → openclaw descarga bytes → POST http://localhost:8002/ocr
  → worker: Tesseract → [si baja calidad] Gemini 2.5 Flash
  → persist en Postgres (receipt + 43 line_items)
  → JSON summary → openclaw formatea → reply en Telegram
  → dashboard en http://localhost:8001 muestra la boleta por mes
```

Primera boleta real procesada: **LIDER, $194.330, 43 ítems** — extraída completamente por Gemini 2.5 Flash, visible en el dashboard en el mes correcto.

---

## Modelo OCR activo

| Motor | Modelo | Uso | Costo |
|---|---|---|---|
| Primario | Tesseract PSM 4 OEM 1 spa | Siempre primero | Gratis |
| Fallback | **Gemini 2.5 Flash** (`gemini-2.5-flash`) | Conf < 65% o ítems < 20 + validación falla | ~$0.0002/foto |

**Por qué `gemini-2.5-flash`:** Es el modelo multimodal más capaz disponible y confirmado en la cuenta. `gemini-1.5-flash` fue deprecado de la API v1beta (retorna 404). `gemini-3.1-flash-lite` existe y es más barato, pero tiene menor precisión en visión — crítico cuando se extraen precios de boletas.

**SDK:** Se usa `google.generativeai` (nombre de modelo sin prefijo `google/`). Este SDK está marcado como deprecated; migrar a `google.genai` en una sesión futura. No es urgente — funciona.

---

## Decisiones de diseño tomadas

### Fecha fallback cuando Gemini no la encuentra

**Problema:** Gemini no siempre puede leer la fecha de la foto (tinta desvanecida, ángulo, zona recortada). Si `issued_date = NULL`, el dashboard filtra todas las queries por mes y el recibo se vuelve invisible.

**Decisión:** cuando `gemini_extract()` no parsea fecha, usa `date.today()` — la fecha en que el usuario envía la foto al bot. Es semánticamente correcta: si no sabemos cuándo compraron, la fecha de registro es el mejor aproximado.

**Dónde está el fix:** `worker/gemini_ocr.py`, tras `parse_date()`:
```python
if issued is None:
    issued = date.today()
```

**Adicionalmente:** `dashboard/queries.py` y las vistas SQL (`v_monthly_spend_by_category`, `v_spend_by_merchant`) usan `COALESCE(issued_date, created_at::date)` como red de seguridad para datos históricos.

### Los line_items de Gemini son idénticos a los de Tesseract

El fallback Gemini devuelve el mismo dict que `extract_from_bytes`: `line_items` con `line_no`, `raw_text`, `normalized_name`, `qty`, `unit_price`, `line_total`. `db.persist()` los inserta en la tabla `line_items` exactamente igual. No hay diferencia de comportamiento entre motores desde la perspectiva del dashboard.

### Idempotencia por `image_sha256`

La misma foto enviada dos veces → `status: "duplicate"`, no se duplica en la DB. Si el motor de extracción cambia entre envíos (ej. primera vez Tesseract fallando, segunda vez Gemini exitoso), el segundo intento no sobreescribe porque el conflict es por hash de imagen. Implica que si se quiere re-procesar una foto con mejor extracción, hay que borrar el recibo primero.

---

## Estado de la base de datos

```sql
-- Tablas activas
receipts      -- 1 fila (primera boleta real)
line_items    -- 43 filas (todos los ítems de la boleta LIDER)
merchants     -- 1 fila (LIDER, sin RUT — extraído de foto)
categories    -- seed completo (13 categorías raíz + subcategorías)
item_aliases  -- seed con ~34 reglas deterministas

-- Vistas
v_monthly_spend_by_category  -- usada por dashboard (category_breakdown)
v_spend_by_merchant          -- usada por dashboard (top_merchants)
v_item_price_history         -- histórico de precios por producto
v_uncategorized_items        -- para poblar item_aliases
v_tax_reconciliation         -- detector de errores OCR
```

**Próximo paso inmediato:** poblar `item_aliases` con los ítems reales de `v_uncategorized_items` para que el dashboard clasifique los gastos por categoría (hoy todos aparecen como "Sin categoria").

---

## Contenedores en producción

| Container | Puerto host | Rol |
|---|---|---|
| `fortunia-worker-1` | 8002 | FastAPI OCR, recibe fotos de openclaw |
| `fortunia-dashboard-1` | 8001 | Dashboard web (FastAPI + Jinja2 + HTMX) |
| `fortunia-postgres-1` | 5432 | Base de datos |
| `fortunia-db-backup-1` | — | pg_dump nightly → ./backups |

openclaw corre fuera de docker en el Mac mini y llama al worker en `http://localhost:8002/ocr`.

---

## Qué falta / siguientes pasos

1. **Categorización real:** poblar `item_aliases` desde `v_uncategorized_items` para que los 43 ítems de la primera boleta queden clasificados. Actualmente todo es "Sin categoria".

2. **Migrar SDK Gemini:** de `google.generativeai` (deprecated) a `google.genai`. No urgente; funciona.

3. **Manejo de `status: "duplicate"** en openclaw**: hoy responde "Ya tenía esa boleta". Podría mostrar el `receipt_id` existente con un link.

4. **Re-procesamiento de boletas:** si se quiere mejorar una boleta ya guardada (ej. foto de mejor calidad), hay que borrar el recibo y re-enviar. Evaluar si conviene un endpoint `PUT /ocr/{receipt_id}`.

5. **Merchants sin RUT:** LIDER fue guardado sin RUT porque la foto no tenía barcode legible. Si en el futuro se escanea otra boleta de LIDER con barcode, se creará un segundo merchant. Evaluar merge por `normalized_name` cuando no hay RUT.
