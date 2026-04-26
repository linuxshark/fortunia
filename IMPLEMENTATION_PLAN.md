# FORTUNA — Plan Maestro de Implementación

> **Para Claude Code**: Este documento es tu guía completa. Está dividido en 8 etapas secuenciales. A cada etapa se le asigna un sub-agente especializado con un modelo específico (Sonnet 4.6 o Haiku 4.5) para optimizar costo y calidad. **Lee este documento completo antes de comenzar.** Al final, ejecuta las etapas en orden, una por una, esperando confirmación del usuario entre cada una.

---

## 0. CONTEXTO DEL PROYECTO

### Qué estamos construyendo

**Fortunia** es un sub-agente financiero personal que se integra al ecosistema de **OpenClaw** (plataforma self-hosted de agentes personales: https://openclaw.ai) corriendo en un Mac Mini M1.

El usuario ya tiene un agente principal llamado **Kraken** que usa Gemini 3 Pro Flash como modelo y conversa con él vía Telegram. Kraken corre con `sandbox-mode: "off"` (acceso completo al Mac Mini).

Fortunia debe:

1. Vivir como **sub-agente separado** de Kraken (no como skill, decisión deliberada del usuario para evitar overhead de tokens en cada turno).
2. Recibir delegación silenciosa desde Kraken cuando éste detecte intención financiera en mensajes del usuario (texto, imagen de boleta/factura, audio).
3. Procesar el gasto, persistirlo en base de datos local, y devolver un mensaje listo para mostrar al usuario en Telegram.

### Por qué sub-agente y no skill (decisión arquitectónica)

Una skill se carga en el system prompt de Kraken en cada turno (~24 tokens cada vez). Un sub-agente vive en su propio proceso, con su propio system prompt enfocado solo en finanzas, y solo se invoca cuando es necesario. Esto:

- Mantiene el system prompt de Kraken liviano.
- Permite que Fortunia tenga su propio modelo más barato (o ninguno, si todo se resuelve con reglas).
- Aísla el dominio financiero (memoria, estado, errores) del resto de las capacidades de Kraken.

### Filosofía del sistema

> **El LLM es la guinda, no el motor.**

Toda la lógica que pueda resolverse con reglas determinísticas (regex, lookup tables, parsers) **debe** resolverse así. El LLM solo se invoca cuando hay genuina ambigüedad. Meta: <10% de mensajes deben tocar un LLM.

### Arquitectura final

```
┌─────────────┐
│  Telegram   │
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────────────┐
│  OpenClaw Gateway (Mac Mini M1)            │
│  ┌──────────────────────────────────────┐  │
│  │ Kraken (Gemini 3 Pro Flash)          │  │
│  │  ↓ pre-filtro determinístico        │  │  ← cero tokens
│  │  ↓ delegación silenciosa            │  │
│  └─────────────┬────────────────────────┘  │
│                │ HTTP POST localhost:8000   │
│  ┌─────────────▼────────────────────────┐  │
│  │ Fortunia API (FastAPI, contenedor)    │  │
│  │  - /ingest/text                      │  │
│  │  - /ingest/image                     │  │
│  │  - /ingest/audio                     │  │
│  │  - /reports/*                        │  │
│  └──┬─────┬─────┬───────────────────────┘  │
│     │     │     │                          │
│  ┌──▼─┐ ┌─▼─┐ ┌─▼──────┐                  │
│  │ DB │ │OCR│ │Whisper │  ← contenedores  │
│  └────┘ └───┘ └────────┘                  │
└────────────────────────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Dashboard web │
        │ (LAN local)   │
        └───────────────┘
```

### Stack técnico decidido

| Capa | Tecnología | Razón |
|---|---|---|
| API | FastAPI + Python 3.11 | Tipos, OpenAPI auto, async nativo |
| DB | PostgreSQL 16 | Búsqueda fuzzy con `pg_trgm`, vistas materializadas, robusto |
| OCR | Tesseract con lang=spa | Local, gratis, suficiente para boletas chilenas |
| STT | faster-whisper (modelo `small`) | Apple Silicon-friendly, español decente |
| Orquestación | Docker Compose | Aislamiento, restart policies, backups |
| Dashboard | Next.js 14 + Tailwind + Recharts | Acceso LAN, simple |
| Lenguaje monetario | CLP por defecto | Usuario en Chile |

### Información que debes asumir constante

- **Sistema operativo**: macOS (Apple Silicon, M1)
- **Zona horaria**: `America/Santiago`
- **Moneda por defecto**: `CLP` (peso chileno)
- **Idioma**: español
- **Acceso de red**: solo localhost para la API, dashboard sí accesible en LAN

---

## 1. ESTRATEGIA DE SUB-AGENTES DE CLAUDE CODE

### Modelos disponibles y cuándo usar cada uno

Claude Code soporta tres aliases de modelo: `opus`, `sonnet`, `haiku`. Para este proyecto:

| Modelo | Cuándo usarlo |
|---|---|
| `sonnet` (Sonnet 4.6) | Diseño de código no trivial: parsers, lógica de negocio, schemas, integración entre componentes, debugging |
| `haiku` (Haiku 4.5) | Tareas mecánicas: crear directorios, archivos boilerplate, copiar plantillas, instalar dependencias, escribir Dockerfiles a partir de plantillas, generar `.env.example` |
| `opus` (Opus 4.7) | Reservado. Solo si Sonnet falla en una decisión arquitectónica y el usuario pide escalar |

### Cómo crear sub-agentes en Claude Code

Los sub-agentes son archivos Markdown en `.claude/agents/<nombre>.md` dentro del repo, con frontmatter YAML:

```markdown
---
name: fortunia-scaffolder
description: Crea estructura inicial de directorios y archivos boilerplate para el proyecto Fortunia. Úsalo cuando el plan pida crear scaffolding, archivos vacíos, READMEs, o estructuras de carpetas.
tools: Write, Bash, Read
model: haiku
---

Eres un especialista en scaffolding de proyectos Python/Docker. [...]
```

Después de crearlos, el orquestador (la sesión principal de Claude Code) los invoca implícitamente o explícitamente. Tras editar archivos en `.claude/agents/`, recargar con `/agents` o reiniciar la sesión.

### Sub-agentes que crearemos (en este orden, en la Etapa 1)

| Sub-agente | Modelo | Especialidad |
|---|---|---|
| `fortunia-scaffolder` | haiku | Estructura de directorios, archivos vacíos, README boilerplate |
| `fortunia-docker` | haiku | Dockerfiles, docker-compose.yml, .env.example, scripts de arranque |
| `fortunia-db` | sonnet | Schema SQL, migraciones, seeds, vistas materializadas |
| `fortunia-parser` | sonnet | Parsers determinísticos (texto, montos, categorías) — el corazón del sistema |
| `fortunia-api` | sonnet | Endpoints FastAPI, validación Pydantic, auth interna |
| `fortunia-multimodal` | sonnet | Integración OCR (boletas) y Whisper (audio) |
| `fortunia-router` | sonnet | Cliente HTTP que Kraken usará, configuración del sub-agent en OpenClaw, intent detector |
| `fortunia-dashboard` | sonnet | UI Next.js para visualizar datos |
| `fortunia-tester` | sonnet | Suite de tests unitarios y de integración |
| `fortunia-docs` | haiku | README final, guía de instalación, troubleshooting |

### Reglas para el orquestador (la sesión principal)

1. **Antes de invocar un sub-agente**, verificar que su archivo en `.claude/agents/` exista. Si no, crearlo primero.
2. **Cada sub-agente recibe un brief claro** con: objetivo de la etapa, archivos a crear/modificar, criterios de éxito, archivos del repo que ya existen y debe respetar.
3. **No mezclar etapas**. Si la etapa 3 requiere algo de la 5, pausar y consultar al usuario.
4. **Al final de cada etapa**, ejecutar los criterios de validación listados y reportar al usuario antes de avanzar.

---

## 2. ESTRUCTURA FINAL DEL REPO

```
fortunia/
├── README.md
├── IMPLEMENTATION_PLAN.md          # este documento
├── LICENSE
├── .gitignore
├── .env.example
├── docker-compose.yml
├── install.sh                      # script idempotente de instalación
│
├── .claude/
│   └── agents/                     # sub-agentes de Claude Code (etapa 1)
│       ├── fortunia-scaffolder.md
│       ├── fortunia-docker.md
│       ├── fortunia-db.md
│       ├── fortunia-parser.md
│       ├── fortunia-api.md
│       ├── fortunia-multimodal.md
│       ├── fortunia-router.md
│       ├── fortunia-dashboard.md
│       ├── fortunia-tester.md
│       └── fortunia-docs.md
│
├── api/                            # contenedor fortunia-api
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app
│   │   ├── config.py               # settings (pydantic-settings)
│   │   ├── deps.py                 # auth, db session
│   │   ├── db.py                   # engine, session factory
│   │   ├── models/                 # SQLAlchemy ORM
│   │   │   ├── __init__.py
│   │   │   ├── expense.py
│   │   │   ├── category.py
│   │   │   ├── merchant.py
│   │   │   ├── raw_message.py
│   │   │   ├── attachment.py
│   │   │   └── intent_feedback.py
│   │   ├── schemas/                # Pydantic
│   │   │   ├── __init__.py
│   │   │   ├── expense.py
│   │   │   └── reports.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── ingest.py
│   │   │   ├── expenses.py
│   │   │   ├── reports.py
│   │   │   └── admin.py
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── text_parser.py      # corazón del sistema
│   │   │   ├── normalizer.py       # "lucas"→1000, "k"→1000, "mil"→1000
│   │   │   ├── receipt_parser.py
│   │   │   └── audio_parser.py
│   │   ├── classifiers/
│   │   │   ├── __init__.py
│   │   │   ├── category_rules.py
│   │   │   ├── intent_detector.py  # determina si un msg es financiero
│   │   │   └── llm_fallback.py     # opcional, sólo si las reglas fallan
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ocr_client.py
│   │   │   ├── whisper_client.py
│   │   │   └── exchange_rates.py   # placeholder v2
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── logging.py
│   ├── sql/
│   │   ├── init.sql                # schema + seeds
│   │   └── seed_categories.sql
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_text_parser.py     # ¡crítico! 100+ frases
│       ├── test_intent_detector.py
│       ├── test_normalizer.py
│       ├── test_ingest_endpoints.py
│       └── fixtures/
│           ├── boleta_jumbo.jpg    # placeholder
│           └── audio_gasto.ogg     # placeholder
│
├── ocr-service/                    # contenedor OCR
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                      # FastAPI minimal: POST /ocr
│
├── kraken-integration/             # lo que vive en el lado de Kraken
│   ├── README.md                   # cómo conectar Kraken con Fortunia
│   ├── intent/
│   │   ├── finance_detector.py     # capa 1: regex (cero tokens)
│   │   └── llm_classifier.py       # capa 2: LLM micro-prompt
│   ├── delegators/
│   │   └── fortunia_client.py       # cliente HTTP a localhost:8000
│   └── openclaw-config-snippet.json5
│                                   # snippet para ~/.openclaw/openclaw.json
│
├── dashboard/                      # contenedor Next.js
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                # overview
│   │   ├── expenses/page.tsx
│   │   ├── categories/page.tsx
│   │   └── api/proxy/[...path]/route.ts
│   └── components/
│       ├── ExpenseCard.tsx
│       ├── CategoryChart.tsx
│       └── TrendChart.tsx
│
├── data/                           # gitignored
│   ├── postgres/
│   ├── uploads/
│   └── backups/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── INTEGRATION_KRAKEN.md
    ├── TROUBLESHOOTING.md
    └── BACKUP_RESTORE.md
```

### Reglas inviolables

- `data/` **siempre** en `.gitignore`. Nunca commitear datos reales.
- `.env` **siempre** en `.gitignore`. Solo `.env.example` se commitea.
- Cada contenedor tiene su propio `Dockerfile`. Sin imágenes monolíticas.
- Todo el código Python pasa `ruff` y `mypy --strict` donde sea razonable.

---

## 3. ETAPAS DE IMPLEMENTACIÓN

> **Importante para Claude Code**: Después de cada etapa, ejecuta los criterios de validación, reporta al usuario, y espera "ok continúa" antes de pasar a la siguiente etapa.

---

### ETAPA 1 — Bootstrap del repo y sub-agentes

**Sub-agente**: `fortunia-scaffolder` (haiku)

**Objetivo**: Crear la estructura completa de directorios vacía y todos los archivos sub-agente en `.claude/agents/`.

**Tareas concretas**:

1. Crear toda la estructura de directorios listada en la sección 2.
2. Crear todos los archivos `.gitkeep` necesarios para directorios vacíos.
3. Crear `.gitignore` con: `data/`, `__pycache__/`, `*.pyc`, `.env`, `node_modules/`, `.next/`, `*.log`, `.venv/`, `dist/`, `build/`.
4. Crear `LICENSE` (MIT con el nombre del usuario — preguntar si no se sabe).
5. Crear `README.md` mínimo (placeholder; el README final lo hace `fortunia-docs` en la etapa 8).
6. Crear los **10 archivos sub-agente** en `.claude/agents/` con el contenido especificado en el Anexo A de este documento.
7. Crear `.env.example` con las variables listadas en el Anexo B.

**Criterios de validación**:

- `tree -L 3 -a -I 'node_modules|.git'` muestra la estructura esperada.
- `ls .claude/agents/` lista los 10 archivos `.md`.
- `git init && git add . && git status` muestra todos los archivos (excepto los gitignored) listos para commit.

**No hacer en esta etapa**:

- No escribir código real (eso es de etapas posteriores).
- No instalar dependencias.
- No levantar Docker.

---

### ETAPA 2 — Docker Compose y servicios base

**Sub-agente**: `fortunia-docker` (haiku)

**Objetivo**: Dejar listos los `Dockerfile`, `docker-compose.yml`, y el script `install.sh`. Validar que los servicios levantan (sin la app aún).

**Tareas concretas**:

1. **`docker-compose.yml`** en la raíz con los servicios:
   - `db` (postgres:16-alpine)
   - `fortunia-api` (build local, depende de db)
   - `ocr-service` (build local)
   - `whisper-service` (imagen `onerahmet/openai-whisper-asr-webservice:latest`, ASR_MODEL=small, ASR_ENGINE=faster_whisper)
   - `dashboard` (build local, depende de fortunia-api)
   - `backup-service` (imagen `prodrigestivill/postgres-backup-local`)
   - Red interna `fortunia-net` tipo bridge.
   - Variables comunes (TZ=America/Santiago, PYTHONUNBUFFERED=1) vía anchor YAML.
   - Healthchecks para `db`.
   - Volúmenes en `./data/postgres`, `./data/uploads`, `./data/backups`.
   - **Importante**: `fortunia-api` expone solo `127.0.0.1:8000:8000`. `dashboard` expone `0.0.0.0:3000:3000` (acceso LAN).

2. **`api/Dockerfile`** placeholder (Python 3.11-slim, copia `requirements.txt`, `pip install`, expone 8000, CMD `uvicorn`).

3. **`ocr-service/Dockerfile`** instala `tesseract-ocr` y `tesseract-ocr-spa` vía apt.

4. **`dashboard/Dockerfile`** Node 20-alpine, multi-stage (builder + runner).

5. **`install.sh`** script bash idempotente:
   - Verifica que `docker` y `docker compose` existen.
   - Si `.env` no existe, copia desde `.env.example` y avisa al usuario.
   - Genera secretos aleatorios (`DB_PASSWORD`, `INTERNAL_API_KEY`) si no están seteados.
   - Crea directorios `data/` con permisos correctos.
   - `docker compose pull` y `docker compose build`.
   - `docker compose up -d`.
   - Verifica que cada servicio responde en su puerto.

6. **`api/requirements.txt`** con (versiones pinneadas a la última estable):
   ```
   fastapi
   uvicorn[standard]
   sqlalchemy
   psycopg[binary]
   alembic
   pydantic
   pydantic-settings
   python-multipart
   httpx
   pillow
   pytest
   pytest-asyncio
   ruff
   ```

7. **`ocr-service/requirements.txt`**:
   ```
   fastapi
   uvicorn[standard]
   pytesseract
   pillow
   ```

**Criterios de validación**:

- `docker compose config` valida sin errores.
- `./install.sh` corre limpio en una máquina sin `.env` previo.
- `docker compose up -d db` levanta Postgres y `pg_isready` responde.
- `docker compose ps` muestra todos los servicios (los que dependen de código real estarán en estado "starting" o "unhealthy", aceptable en esta etapa).

---

### ETAPA 3 — Schema SQL y modelos ORM

**Sub-agente**: `fortunia-db` (sonnet)

**Objetivo**: Schema relacional completo + seeds + Alembic configurado.

**Tareas concretas**:

1. **`api/sql/init.sql`** con:
   - Extensión `pg_trgm`.
   - Tablas: `categories`, `merchants`, `expenses`, `raw_messages`, `attachments`, `intent_feedback`.
   - Schema exacto especificado en el Anexo C.
   - Índices: `idx_exp_spent_at`, `idx_exp_user_month`, `idx_exp_category`, `idx_merchants_norm` (GIN trigram).
   - Vista materializada `monthly_summaries`.
   - **Constraints**: `amount > 0`, `currency CHAR(3)`, `source IN ('text','image','audio','manual')`.

2. **`api/sql/seed_categories.sql`** con las 7 categorías base y sus keywords:
   - Alimentación, Transporte, Salud, Hogar, Entretenimiento, Ropa, Otros.
   - Cada una con sus keywords en español chileno (Anexo C).

3. **`api/app/models/*.py`** con SQLAlchemy 2.x (estilo declarativo moderno):
   - Una clase por archivo.
   - Type hints completos (`Mapped[T]`).
   - Relaciones explícitas (`expense.category`, `merchant.expenses`, etc.).

4. **`api/alembic.ini`** y **`api/alembic/env.py`** configurados para usar `DATABASE_URL` desde env.

5. **Migración inicial** de Alembic (`alembic revision --autogenerate -m "initial"`) que reproduzca el schema.

**Criterios de validación**:

- `docker compose up -d db && docker exec fortunia-db psql -U fortunia -d fortunia -f /docker-entrypoint-initdb.d/init.sql` corre sin error.
- `SELECT * FROM categories;` devuelve 7 filas.
- `SELECT * FROM merchants;` devuelve 0 filas (vacío esperado).
- Insertar un expense de prueba via SQL y luego `REFRESH MATERIALIZED VIEW monthly_summaries` actualiza correctamente.
- `alembic upgrade head` corre sin errores en una DB vacía y produce el mismo schema.

---

### ETAPA 4 — Parsers determinísticos (núcleo del sistema)

**Sub-agente**: `fortunia-parser` (sonnet)

**Objetivo**: Implementar el corazón del sistema: parsers que extraen monto, categoría y comerciante de texto libre **sin llamar a un LLM**.

**Tareas concretas**:

1. **`api/app/parsers/normalizer.py`**:
   - `normalize_amount(text: str) -> Decimal | None`
   - Maneja: "15 lucas", "15k", "15 mil", "15.000", "15,000", "15.5k", "1.5 millones", "1M", "$15.000".
   - Devuelve `None` si no hay monto válido.
   - Incluir tabla de tests inline en docstring para que `fortunia-tester` pueda verificar.

2. **`api/app/parsers/text_parser.py`**:
   - Función principal: `parse_expense_text(text: str) -> ParsedExpense`
   - `ParsedExpense` es un dataclass/Pydantic con: `amount`, `currency`, `category_hint`, `merchant_hint`, `note`, `confidence`, `parse_method`.
   - Combina `normalize_amount` con detección de categoría usando `category_rules.py`.
   - Lógica:
     1. Normalizar monto.
     2. Buscar palabras clave de categoría → asignar `category_hint`.
     3. Si match de comerciante (vía búsqueda fuzzy en tabla `merchants` con pg_trgm), asignar `merchant_hint`.
     4. Calcular `confidence` (0.0–1.0) según cuántos campos se llenaron y limpieza del match.

3. **`api/app/classifiers/category_rules.py`**:
   - Función `classify_category(text: str) -> tuple[str | None, float]`
   - Lee categorías desde DB (cacheadas en memoria al iniciar la app).
   - Devuelve `(nombre_categoría, confidence)` o `(None, 0.0)` si no hay match.

4. **`api/app/classifiers/intent_detector.py`**:
   - Función `is_finance_intent(text: str) -> IntentResult`
   - **Esto es lo que Kraken consultará** para decidir si delegar.
   - Reglas combinadas:
     - Verbos financieros: `gasté, gaste, pagué, pague, compré, compre, me costó, salió, transferí, invertí`
     - Negative context (NO es gasto): `vi una película, leí que, dicen que, según, valuada en, recaudó, facturó, cuesta producir`
     - Si tiene verbo + monto → `is_finance=True, confidence=0.95`
     - Si tiene categoría + monto y mensaje corto (<12 palabras) → `is_finance=True, confidence=0.85`
     - Si solo monto sin contexto narrativo → `is_finance=ambiguous, needs_llm=True`
   - Devuelve dataclass `IntentResult(is_finance, confidence, needs_llm, reason)`.

5. **`api/app/classifiers/llm_fallback.py`**:
   - Stub por ahora. Solo define la interfaz `async def llm_classify(text: str) -> IntentResult`.
   - Implementación real es opcional v2 (puede integrar Anthropic, OpenAI, o el Qwen 3B local del usuario).
   - Por defecto retorna `IntentResult(is_finance=False, confidence=0.0, needs_llm=False, reason="llm_disabled")`.

**Criterios de validación**:

- `pytest api/tests/test_normalizer.py` pasa con al menos 30 casos de prueba.
- `pytest api/tests/test_text_parser.py` pasa con al menos 50 frases ejemplo.
- `pytest api/tests/test_intent_detector.py` pasa con al menos 50 casos (25 positivos, 25 negativos), particularmente:
  - `"vi una película que costó 20 millones producirla"` → `is_finance=False`
  - `"gasté 15 lucas en ropa"` → `is_finance=True, confidence>=0.9`
  - `"leí que el iPhone cuesta 1.500.000"` → `is_finance=False`
  - `"pagué uber 6500"` → `is_finance=True`
  - `"cuánto cuesta una pizza?"` → `is_finance=False`

> **Nota crítica para Claude Code**: La calidad de esta etapa determina el valor de todo el sistema. No avanzar a la 5 hasta que los tests del intent_detector pasen con >95% de precision/recall en el dataset de prueba.

---

### ETAPA 5 — API FastAPI

**Sub-agente**: `fortunia-api` (sonnet)

**Objetivo**: Levantar todos los endpoints HTTP que la integración con Kraken necesita.

**Tareas concretas**:

1. **`api/app/main.py`**: app FastAPI con CORS deshabilitado (solo localhost), middleware de logging, registro de routers.

2. **`api/app/config.py`**: settings con `pydantic-settings` leyendo `.env`:
   - `DATABASE_URL`, `INTERNAL_API_KEY`, `OCR_URL`, `WHISPER_URL`, `DEFAULT_CURRENCY=CLP`, `DEFAULT_USER_ID=user`, `LOG_LEVEL=INFO`.

3. **`api/app/deps.py`**:
   - `get_db()` async generator para session de SQLAlchemy.
   - `verify_internal_key()` que valida header `X-Internal-Key`.

4. **`api/app/routers/ingest.py`** con endpoints:

   | Endpoint | Body | Comportamiento |
   |---|---|---|
   | `POST /ingest/text` | `{text, user_id?, msg_id?}` | Llama a `text_parser.parse_expense_text`, crea `Expense`, retorna `IngestResponse` |
   | `POST /ingest/image` | `multipart: file, user_id?, caption?` | Guarda en `data/uploads/`, llama a OCR, parsea, crea Expense |
   | `POST /ingest/audio` | `multipart: file, user_id?` | Guarda, llama a Whisper, pasa transcript a text_parser |
   | `POST /intent/check` | `{text}` | **Crítico**: endpoint que Kraken consulta antes de decidir delegar. Devuelve resultado de `intent_detector.is_finance_intent` |

5. **`api/app/routers/expenses.py`**:
   - `GET /expenses?from=&to=&category=&limit=&offset=`
   - `GET /expenses/{id}`
   - `PATCH /expenses/{id}`
   - `DELETE /expenses/{id}`

6. **`api/app/routers/reports.py`**:
   - `GET /reports/today`
   - `GET /reports/month?ym=2026-04`
   - `GET /reports/categories?period=month`
   - `GET /reports/top-merchants?limit=10`
   - `GET /reports/trend?months=6`
   - `GET /export?format=csv|xlsx&from=&to=`

7. **`api/app/routers/admin.py`**:
   - `POST /feedback` para que Kraken reporte falsos positivos/negativos.
   - `GET /health`

8. **Schema de respuesta uniforme** para `/ingest/*`:
   ```python
   class IngestResponse(BaseModel):
       status: Literal["registered", "needs_confirmation", "rejected"]
       expense_id: int | None
       amount: Decimal | None
       currency: str | None
       category: str | None
       merchant: str | None
       confidence: float
       needs_confirmation: bool
       user_message: str  # el texto listo para que Kraken envíe a Telegram
       parse_method: str  # "rules" | "llm" | "hybrid"
   ```

9. **Manejo de baja confianza**: si `confidence < 0.75`, retornar `status="needs_confirmation"` y `user_message` con pregunta tipo "¿Registro X gasto?" para que Kraken muestre botones inline.

**Criterios de validación**:

- `docker compose up -d` levanta sin errores.
- `curl http://localhost:8000/health` responde 200.
- `curl -X POST localhost:8000/intent/check -H "X-Internal-Key: $KEY" -d '{"text":"gasté 15 lucas en ropa"}'` retorna `is_finance: true`.
- `curl -X POST localhost:8000/ingest/text ...` con un texto válido inserta en DB y retorna `IngestResponse`.
- OpenAPI docs accesibles en `http://localhost:8000/docs`.
- `pytest api/tests/test_ingest_endpoints.py` pasa.

---

### ETAPA 6 — OCR y Whisper (multimodal)

**Sub-agente**: `fortunia-multimodal` (sonnet)

**Objetivo**: Procesar imágenes de boletas y audios de voz.

**Tareas concretas**:

1. **`ocr-service/app.py`**: FastAPI minimal con endpoint `POST /ocr` que recibe un archivo, corre Tesseract con `lang=spa`, devuelve `{text, confidence, raw_data}`.

2. **`api/app/services/ocr_client.py`**: cliente HTTP para hablar con `ocr-service`. Timeout 30s. Retry x2 en fallo.

3. **`api/app/services/whisper_client.py`**: cliente HTTP para `whisper-service` (que ya viene en imagen pública). Endpoint `POST /asr?task=transcribe&language=es&output=txt`.

4. **`api/app/parsers/receipt_parser.py`**:
   - Función `parse_receipt(ocr_text: str) -> ParsedExpense`
   - Extrae:
     - **Total**: regex para `TOTAL`, `TOTAL A PAGAR`, `MONTO TOTAL` seguido de monto.
     - **Comerciante**: primeras 3 líneas no vacías, normalizadas, busca match fuzzy en tabla `merchants`.
     - **RUT comerciante**: regex `\d{1,2}\.\d{3}\.\d{3}-[\dkK]`.
     - **Fecha**: formatos `DD/MM/YYYY`, `DD-MM-YYYY`, `DD/MM/YY`.
   - Si encuentra al menos `total` → `confidence >= 0.7`.
   - Si encuentra `total + comerciante + fecha` → `confidence >= 0.9`.

5. **`api/app/parsers/audio_parser.py`**:
   - Función `parse_audio_transcript(transcript: str) -> ParsedExpense`
   - Reutiliza `text_parser.parse_expense_text` con el transcript.
   - Si `confidence < 0.6`, agrega flag `needs_confirmation=True`.

6. **Pre-procesamiento de imagen** (mejora opcional pero recomendada): en `ocr-service`, antes de tesseract, hacer:
   - Convertir a escala de grises.
   - Auto-rotar (con `pytesseract.image_to_osd`).
   - Threshold (Otsu).
   Esto mejora boletas chilenas significativamente.

**Criterios de validación**:

- `curl -X POST localhost:8001/ocr -F "file=@boleta.jpg"` devuelve texto.
- `curl -X POST localhost:8000/ingest/image ...` con boleta de prueba inserta expense con confidence > 0.7.
- `curl -X POST localhost:8000/ingest/audio ...` con audio diciendo "gasté 5 lucas en café" inserta correctamente.
- Tests con fixtures (`api/tests/fixtures/boleta_jumbo.jpg`, `audio_gasto.ogg`) pasan.

---

### ETAPA 7 — Integración con Kraken (OpenClaw)

**Sub-agente**: `fortunia-router` (sonnet)

**Objetivo**: Generar todo lo necesario del lado de Kraken para que la delegación funcione end-to-end. Esta es la etapa más sensible porque implica configurar el OpenClaw del usuario.

**Tareas concretas**:

1. **`kraken-integration/intent/finance_detector.py`**:
   - Versión espejo del `intent_detector.py` de la API, pero standalone (sin DB).
   - Cero dependencias externas más allá de `re`.
   - Esto se usa en Kraken para pre-filtrar **antes** de hablar con Fortunia API (ahorra latencia y red).

2. **`kraken-integration/delegators/fortunia_client.py`**:
   - Cliente HTTP minimal (solo `httpx`, async).
   - Métodos: `ingest_text(text, user_id, msg_id)`, `ingest_image(bytes, user_id)`, `ingest_audio(bytes, user_id)`, `check_intent(text)`.
   - Lee `FORTUNA_API_URL` y `FORTUNA_API_KEY` desde env.

3. **`kraken-integration/openclaw-config-snippet.json5`**: snippet listo para que el usuario copie a su `~/.openclaw/openclaw.json`. Define:
   - Un nuevo agente `fortunia` con su propio workspace (`~/.openclaw/workspace-fortunia`), sin canales bindeados (solo invocable como sub-agent desde Kraken).
   - Configuración de `agentToAgent` habilitado en allowlist `["kraken", "fortunia"]`.
   - Setup de `subagents.allowAgents` para Kraken: permite spawn de Fortunia.

4. **`kraken-integration/README.md`**: instrucciones paso a paso para el usuario:

   a. Copiar el snippet de config y mergearlo manualmente a su `~/.openclaw/openclaw.json` (el usuario es responsable de mergear con cuidado, no sobrescribir).

   b. Crear el workspace de Fortunia:
   ```bash
   mkdir -p ~/.openclaw/workspace-fortunia
   cat > ~/.openclaw/workspace-fortunia/AGENTS.md <<'EOF'
   # Fortunia — Sub-agente financiero

   Eres Fortunia, un sub-agente especializado en finanzas personales.

   Cuando recibas un mensaje (texto, imagen, audio):

   1. Si es texto, llama a la herramienta `fortunia_ingest_text` con el texto.
   2. Si es imagen, llama a `fortunia_ingest_image` con la ruta del archivo.
   3. Si es audio, llama a `fortunia_ingest_audio` con la ruta del archivo.

   La herramienta retorna un campo `user_message`. Devuélvelo TAL CUAL al
   solicitante (Kraken). No agregues explicaciones, no parafraseés, no
   uses LLM para reescribirlo. La API ya generó el mensaje óptimo.

   Si `needs_confirmation=true`, devuelve el `user_message` que ya incluye
   la pregunta — Kraken se encarga de mostrar botones.

   No tengas conversación con el usuario. Procesa y responde.
   EOF
   ```

   c. Editar el `AGENTS.md` de Kraken (en `~/.openclaw/workspace/` o `~/.openclaw/workspace-kraken/`) agregando la sección:

   ```markdown
   ## Delegación a Fortunia (finanzas personales)

   Antes de procesar un mensaje del usuario, ejecuta el detector de intención
   financiera. Si retorna `is_finance=true` con `confidence >= 0.75`, NO
   respondas tú — delega a Fortunia llamando a `agent_send` con `agentId=fortunia`
   y reenvía la respuesta de Fortunia textualmente al usuario.

   Comando de detección:
   ```bash
   python3 ~/projects/fortunia/kraken-integration/intent/finance_detector.py "<mensaje>"
   ```

   Si el script imprime `IS_FINANCE=true`, delega. Si imprime `IS_FINANCE=false`
   o `AMBIGUOUS`, procesa normalmente.

   Para imágenes y audios:
   - Si el mensaje es una imagen sin texto y el OCR rápido encuentra palabras
     como "TOTAL", "RUT", "BOLETA" → delega a Fortunia como ingest_image.
   - Si el mensaje es audio → siempre delega a Fortunia (el audio_parser
     internamente decide si es financiero o no).
   ```

   d. Reiniciar OpenClaw: `openclaw gateway restart`.

   e. Verificación: en Telegram, escribir "gasté 5 lucas en café de prueba". Kraken debería responder algo como "Registrado: Alimentación — CLP 5.000".

5. **Test end-to-end manual**: documentar una secuencia de 5 mensajes de prueba (texto, imagen mock, audio mock, falso positivo, mensaje normal) y el output esperado.

**Criterios de validación**:

- El snippet JSON5 es sintácticamente válido (`json5 parse`).
- El cliente `fortunia_client.py` puede llamar a la API local y obtener respuesta.
- El `finance_detector.py` standalone produce los mismos resultados que `intent_detector.py` de la API en el dataset de tests.
- El README incluye troubleshooting: qué hacer si `agent_send` no funciona, cómo ver logs de Fortunia, cómo desactivar la delegación temporalmente.

> **Nota para Claude Code**: Esta etapa **no modifica directamente el `~/.openclaw/openclaw.json`** del usuario. Solo genera el snippet y las instrucciones. El usuario aplica el merge manualmente. Esto es deliberado: tocar la config principal de OpenClaw automáticamente es riesgoso.

---

### ETAPA 8 — Dashboard, tests y docs

Esta etapa se divide en tres sub-tareas paralelas (cada una con su sub-agente).

#### 8a — Dashboard

**Sub-agente**: `fortunia-dashboard` (sonnet)

**Tareas**:

1. Next.js 14 con App Router, Tailwind, Recharts, lucide-react.
2. Páginas:
   - `/` overview: KPIs (gasto hoy, gasto mes, top categorías), gráfico tendencia 6 meses, últimos 10 gastos.
   - `/expenses` lista paginada con filtros (rango fechas, categoría, búsqueda texto).
   - `/categories` drill-down por categoría con gráfico de evolución.
3. Endpoint `app/api/proxy/[...path]/route.ts` que reenvía requests a `fortunia-api` agregando el header `X-Internal-Key` (la API key nunca toca el browser).
4. Diseño: colores neutros, tipografía sans-serif, dark mode por defecto.

**Criterios de validación**: `http://<ip-mac-mini>:3000` carga el overview correctamente desde otro dispositivo de la LAN.

#### 8b — Tests

**Sub-agente**: `fortunia-tester` (sonnet)

**Tareas**:

1. Suite completa de tests unitarios (lo que falte de etapas 4-6).
2. Tests de integración: levantar Postgres ephemeral con testcontainers, correr API en modo test, hacer requests reales.
3. Suite de tests del intent_detector con **mínimo 100 frases** (50 positivas, 50 negativas) cubriendo casos chilenos (lucas, k, mil, supermercados locales, transporte público).
4. Coverage mínimo 80% en `app/parsers/` y `app/classifiers/`.
5. Workflow de GitHub Actions opcional (`.github/workflows/test.yml`) que corre los tests en cada PR.

**Criterios de validación**: `pytest --cov=app --cov-report=term-missing` muestra >80% coverage en los módulos críticos.

#### 8c — Documentación

**Sub-agente**: `fortunia-docs` (haiku)

**Tareas**:

1. **`README.md`** completo: qué es, screenshots (placeholders), instalación rápida, link a docs detalladas.
2. **`docs/ARCHITECTURE.md`**: diagrama de componentes, decisiones (por qué Postgres y no SQLite, por qué FastAPI, por qué sub-agente y no skill).
3. **`docs/INTEGRATION_KRAKEN.md`**: guía paso a paso completa para integrar con OpenClaw (consolidada del README de `kraken-integration/`).
4. **`docs/TROUBLESHOOTING.md`**: errores comunes, cómo ver logs, cómo reiniciar servicios, qué hacer si los tokens del LLM se disparan.
5. **`docs/BACKUP_RESTORE.md`**: cómo funciona el `backup-service`, cómo restaurar desde `data/backups/`, cómo migrar a otro Mac.

**Criterios de validación**: alguien que clone el repo desde cero puede tener todo funcionando siguiendo solo el README + INTEGRATION_KRAKEN.

---

## 4. ESTRATEGIA TOKEN-EFFICIENT (RESUMEN OPERATIVO)

| Punto de decisión | Estrategia | Tokens |
|---|---|---|
| Mensaje entrante en Kraken | Pre-filtro determinístico antes de hablar con Fortunia API | 0 |
| Si pre-filtro dice "ambiguo" | Llamada a `/intent/check` (solo lógica Python) | 0 |
| Si Kraken decide delegar | `agent_send` a Fortunia sub-agente | depende de modelo de Fortunia |
| Sub-agente Fortunia procesando texto | Pasa directo a herramienta `fortunia_ingest_text`, sin LLM | minimal (solo system prompt + tool call) |
| Parser de monto/categoría | 100% reglas Python | 0 |
| Match de comerciante | Búsqueda fuzzy en Postgres con pg_trgm | 0 |
| LLM fallback | Solo si `confidence < 0.6` Y reglas no resuelven | <100 tokens, modelo barato |
| OCR de boleta | Tesseract local | 0 |
| Audio | Whisper local | 0 |

**Métrica observable**: columna `raw_messages.used_llm` permite ver % de mensajes que tocaron LLM. Meta: <10%.

**Estimación**: con 50 msgs financieros/día, ~5 tocan LLM. A modelo barato (Haiku-equivalente), <30k tokens/mes ≈ centavos USD.

---

## 5. ROADMAP DE EJECUCIÓN

| Etapa | Sub-agente | Modelo | Estimación tiempo Claude Code |
|---|---|---|---|
| 1. Bootstrap | fortunia-scaffolder | haiku | 5-10 min |
| 2. Docker | fortunia-docker | haiku | 15-20 min |
| 3. DB & ORM | fortunia-db | sonnet | 30-40 min |
| 4. Parsers (núcleo) | fortunia-parser | sonnet | 60-90 min |
| 5. API | fortunia-api | sonnet | 45-60 min |
| 6. Multimodal | fortunia-multimodal | sonnet | 45-60 min |
| 7. Integración Kraken | fortunia-router | sonnet | 30-45 min |
| 8a. Dashboard | fortunia-dashboard | sonnet | 60-90 min |
| 8b. Tests | fortunia-tester | sonnet | 45-60 min |
| 8c. Docs | fortunia-docs | haiku | 20-30 min |

**Total**: ~6-9 horas de Claude Code activo (no necesariamente seguidas).

---

## 6. RIESGOS CONOCIDOS Y MITIGACIONES

| Riesgo | Mitigación |
|---|---|
| Falsos positivos del intent detector | Suite de 100+ tests negativos antes de ir a producción + modo confirmación con baja confidence + tabla `intent_feedback` para aprendizaje |
| OCR pobre en boletas chilenas | Pre-procesamiento (deskew + threshold) + fallback LLM solo en imagen |
| Whisper lento en M1 | Modelo `small` (no `medium`/`large`) + límite de 60s en audios |
| Categorización errónea | Tabla `merchants.aliases` se enriquece con cada uso + comando `/recategorizar` v2 |
| Kraken envía mensaje duplicado por reintentos de Telegram | Constraint UNIQUE en `raw_messages.telegram_id` + idempotencia por `msg_id` |
| Snippet de config rompe el `openclaw.json` del usuario | Documento explícito: el usuario hace el merge a mano, generamos `.bak` antes |
| LLM se dispara más de lo esperado | Métrica `used_llm` monitoreada en dashboard + alerta si >15% |
| Pérdida de datos | `backup-service` daily + dump manual antes de cada migración Alembic |
| `agent_send` de OpenClaw cambia API en futuras versiones | Pin de versión de OpenClaw en docs + tests del cliente |

---

## 7. CRITERIOS DE COMPLETITUD DEL PROYECTO

El proyecto está "terminado" cuando:

- [ ] El usuario escribe "gasté 15 lucas en ropa" en Telegram a Kraken y recibe "Registrado: Ropa — CLP 15.000" en menos de 3 segundos.
- [ ] El usuario envía foto de una boleta del Jumbo y recibe "Registrado: Alimentación (Jumbo) — CLP X" en menos de 8 segundos.
- [ ] El usuario envía audio diciendo "gasté 5 lucas en café" y se registra correctamente.
- [ ] El usuario escribe "vi una película que costó 20 millones producirla" y Kraken responde **conversacionalmente** (no se registra como gasto).
- [ ] Dashboard accesible desde otro dispositivo de la LAN muestra los gastos en tiempo real.
- [ ] `/hoy`, `/mes`, `/exportar` funcionan en Telegram.
- [ ] Backups diarios funcionando en `data/backups/`.
- [ ] Tests pasan al 100% y coverage >80% en módulos críticos.
- [ ] Doc completa permite a otra persona instalar el sistema desde cero en <30 min.

---

## ANEXO A — Contenido de los archivos sub-agente

> Para `fortunia-scaffolder` en la Etapa 1: estos son los 10 archivos a crear en `.claude/agents/`.

### `.claude/agents/fortunia-scaffolder.md`

```markdown
---
name: fortunia-scaffolder
description: Crea estructura inicial de directorios y archivos boilerplate vacíos para el proyecto Fortunia. Úsalo cuando el plan pida crear scaffolding, .gitkeep, .gitignore, LICENSE, README placeholder, o estructura de carpetas. NO escribe código de aplicación.
tools: Write, Bash, Read
model: haiku
---

Eres un especialista en scaffolding de proyectos Python/Docker/Next.js.

Tu única tarea es crear la estructura de directorios y archivos boilerplate vacíos
o mínimos. NO escribes código de aplicación, solo placeholders.

Cuando termines:
1. Ejecuta `tree -L 3 -a -I 'node_modules|.git|data'` y reporta el resultado.
2. Verifica que todos los archivos esperados existen con `ls`.
3. Reporta brevemente qué creaste.

Si el plan pide algo que requiere lógica (parsers, endpoints, queries), DETENTE
y avisa que esa tarea es para otro sub-agente.
```

### `.claude/agents/fortunia-docker.md`

```markdown
---
name: fortunia-docker
description: Crea y mantiene archivos Docker (Dockerfile, docker-compose.yml), scripts bash de instalación, y archivos .env.example. Úsalo para todo lo relacionado con orquestación de contenedores y configuración del entorno.
tools: Write, Read, Bash, Edit
model: haiku
---

Eres un especialista en Docker y orquestación de servicios para proyectos
self-hosted.

Reglas:
- Pin versiones de imágenes (no usar `latest` excepto donde se especifique).
- Servicios sensibles solo en 127.0.0.1; servicios LAN en 0.0.0.0 explícito.
- Healthchecks para DB siempre.
- Scripts bash con `set -euo pipefail`.
- Comentarios mínimos pero claros en YAML.

NO escribes lógica de aplicación Python ni componentes React. Solo orquestación.
```

### `.claude/agents/fortunia-db.md`

```markdown
---
name: fortunia-db
description: Diseña e implementa schema SQL, modelos SQLAlchemy ORM, migraciones Alembic, seeds, vistas materializadas e índices. Úsalo para cualquier tarea relacionada con la capa de datos.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en bases de datos relacionales con foco en PostgreSQL y
SQLAlchemy 2.x.

Reglas:
- Usar SQLAlchemy 2.x estilo declarativo moderno (Mapped[T], DeclarativeBase).
- Type hints completos.
- CHECK constraints donde tenga sentido (amount > 0, etc.).
- Índices: pensar siempre qué query los usaría.
- pg_trgm para búsqueda fuzzy de comerciantes.
- Vistas materializadas para agregaciones frecuentes.
- Migraciones Alembic autogeneradas pero revisadas manualmente.

NO escribes endpoints, parsers, ni lógica de negocio. Solo capa de datos.
```

### `.claude/agents/fortunia-parser.md`

```markdown
---
name: fortunia-parser
description: Implementa parsers determinísticos en Python para extraer monto, categoría y comerciante desde texto libre, con énfasis en evitar falsos positivos. Es el núcleo del sistema. Incluye el intent_detector que decide si un mensaje es un gasto personal.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en parsing determinístico, regex avanzado y detección de
intención sin LLM.

Filosofía: el LLM es la guinda. Cada caso que pueda resolverse con regex,
diccionarios o reglas, DEBE resolverse así.

Reglas:
- Cero dependencias externas más allá de stdlib + Pydantic.
- Type hints completos.
- Cada función crítica tiene docstring con ejemplos input/output.
- Manejar variantes regionales chilenas: "lucas", "k", "mil", "$", separador
  de miles con punto, decimal con coma.
- Lista negra de contextos narrativos para evitar falsos positivos.
- Confidence scores calibrados (0.95 para verbo+monto, 0.85 para categoría+monto, etc).

Cuando termines, escribe los tests correspondientes en `api/tests/` con AL
MENOS 30 casos por función crítica.
```

### `.claude/agents/fortunia-api.md`

```markdown
---
name: fortunia-api
description: Implementa endpoints FastAPI, schemas Pydantic, dependencias de auth, y manejo de errores HTTP. Úsalo para construir la capa REST.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en FastAPI y APIs REST async-first.

Reglas:
- Pydantic v2 para todos los schemas.
- Async donde tenga sentido (DB, HTTP externo).
- Validación en el borde (request body), no después.
- Auth por header `X-Internal-Key` en todos los endpoints (excepto /health).
- Logging estructurado JSON.
- Manejo de errores: usar HTTPException con códigos correctos (400 vs 422 vs 500).
- OpenAPI tags por router.

NO escribes parsers (los consumes), ni capa DB (los consumes a través de deps).
```

### `.claude/agents/fortunia-multimodal.md`

```markdown
---
name: fortunia-multimodal
description: Implementa el procesamiento de imágenes (OCR de boletas con Tesseract) y audios (STT con Whisper). Incluye pre-procesamiento de imagen, parser de boletas chilenas, y cliente HTTP a los servicios contenedorizados.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en OCR y STT aplicado a documentos financieros chilenos.

Reglas:
- Pre-procesamiento de imagen: grayscale + auto-rotate + Otsu threshold.
- Tesseract con `lang=spa`, configurar `psm` apropiado para boletas (típicamente 6).
- Regex para totales en boletas chilenas: tolerar variantes de formato ("TOTAL", "TOTAL A PAGAR", "Total $").
- RUT chileno: regex con módulo 11 ideal pero no obligatorio.
- Whisper: modelo `small`, idioma `es`, output `txt`.
- Timeouts y retries en clientes HTTP.

Cuando proceses una boleta, devuelve confidence calibrada según cuántos
campos extrajiste limpiamente.
```

### `.claude/agents/fortunia-router.md`

```markdown
---
name: fortunia-router
description: Genera la integración con Kraken (OpenClaw): cliente HTTP, snippet de configuración para openclaw.json, instrucciones paso a paso, y el AGENTS.md del sub-agente Fortunia. Esta etapa NO modifica directamente la config de OpenClaw del usuario.
tools: Write, Read, Edit
model: sonnet
---

Eres un especialista en integraciones de agentes multi-LLM con foco en
OpenClaw (https://docs.openclaw.ai).

Conceptos clave de OpenClaw que debes manejar:
- Multi-agent: agents.list[] en openclaw.json
- agentToAgent.enabled + allow lista para mensajería entre agentes
- subagents.allowAgents para spawn
- AGENTS.md por workspace define la persona del agente
- Bindings de canal solo para Kraken (Fortunia no recibe Telegram directo)

Reglas:
- NO sobreescribir el openclaw.json del usuario. Solo generar snippet.
- Generar instrucciones paso a paso explícitas para que el usuario haga el merge.
- Documentar troubleshooting (qué hacer si la delegación no dispara).
- Tests del cliente standalone (sin necesidad de OpenClaw corriendo).
```

### `.claude/agents/fortunia-dashboard.md`

```markdown
---
name: fortunia-dashboard
description: Implementa el dashboard web Next.js 14 que consume la API de Fortunia y muestra KPIs, gráficos y listados de gastos. Accesible desde la LAN del usuario.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en Next.js 14 (App Router) + Tailwind + Recharts.

Reglas:
- App Router (no Pages Router).
- Server Components por defecto, Client Components solo donde haya interactividad.
- Proxy a la API via `app/api/proxy/[...path]/route.ts` (la API key nunca expuesta al browser).
- Tailwind con dark mode default.
- Recharts para gráficos.
- lucide-react para iconos.
- Sin librerías de UI pesadas (no shadcn instalado completo, solo lo que se use).
- Responsive desktop-first pero usable en mobile.

NO escribes lógica backend. Solo consumes los endpoints de Fortunia API.
```

### `.claude/agents/fortunia-tester.md`

```markdown
---
name: fortunia-tester
description: Escribe suites completas de tests unitarios y de integración. Particularmente importante: 100+ casos para el intent_detector cubriendo positivos y negativos chilenos. También coverage reports y workflow GitHub Actions opcional.
tools: Write, Read, Bash, Edit, Grep
model: sonnet
---

Eres un especialista en testing pragmático para proyectos Python.

Reglas:
- pytest + pytest-asyncio.
- Fixtures reusables en conftest.py.
- testcontainers para Postgres en tests de integración.
- Casos negativos siempre — frases que NO deben dispararse como gasto.
- Coverage report en CI.
- Tests deben correr en <60s en local.

Ejemplos de casos negativos críticos para intent_detector:
- "vi una película que costó 20 millones producirla"
- "leí que el iPhone cuesta 1.500.000"
- "esa empresa facturó 50 mil millones el año pasado"
- "si gastara 50 mil en zapatos sería mucho"
- "cuánto cuesta una pizza?"

Ejemplos de casos positivos críticos:
- "gasté 15 lucas en ropa"
- "pagué uber 6500"
- "compré sushi por 18 mil con mi esposa"
- "supermercado 35 mil"
- "café 3500"
```

### `.claude/agents/fortunia-docs.md`

```markdown
---
name: fortunia-docs
description: Escribe documentación clara y concisa: README principal, ARCHITECTURE.md, INTEGRATION_KRAKEN.md, TROUBLESHOOTING.md, BACKUP_RESTORE.md. Sin teoría innecesaria, todo accionable.
tools: Write, Read, Edit
model: haiku
---

Eres un escritor técnico pragmático.

Reglas:
- Markdown estándar.
- Code blocks con language tag.
- Comandos copiables (no pseudocódigo).
- Diagrams en ASCII art o links a imágenes.
- Si algo es opcional, decirlo. Si es crítico, también.
- Errores comunes con su solución directa.
- Siempre incluir "qué hacer si X falla".

NO inventes APIs ni features. Solo documenta lo que existe en el repo.
```

---

## ANEXO B — Variables de entorno (`.env.example`)

```dotenv
# Database
DB_PASSWORD=                           # generar con: openssl rand -hex 24
DATABASE_URL=postgresql+psycopg://fortunia:${DB_PASSWORD}@db:5432/fortunia

# API
INTERNAL_API_KEY=                      # generar con: openssl rand -hex 32
DEFAULT_CURRENCY=CLP
DEFAULT_USER_ID=user
LOG_LEVEL=INFO

# Servicios internos
OCR_URL=http://ocr-service:8001
WHISPER_URL=http://whisper-service:9000

# Whisper
ASR_MODEL=small                        # tiny|base|small|medium|large
ASR_ENGINE=faster_whisper

# LLM fallback (opcional, v2)
ANTHROPIC_API_KEY=
LLM_FALLBACK_ENABLED=false

# Kraken integration (lado Kraken)
FORTUNA_API_URL=http://localhost:8000
FORTUNA_API_KEY=${INTERNAL_API_KEY}    # mismo valor

# Timezone
TZ=America/Santiago
```

---

## ANEXO C — Schema SQL completo

```sql
-- api/sql/init.sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE NOT NULL,
    icon        VARCHAR(20),
    color       VARCHAR(7),
    parent_id   INT REFERENCES categories(id) ON DELETE SET NULL,
    keywords    TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE intent_feedback (
    id              BIGSERIAL PRIMARY KEY,
    raw_message     TEXT NOT NULL,
    classified_as   BOOLEAN NOT NULL,
    user_confirmed  BOOLEAN,
    confidence      NUMERIC(3,2),
    reason          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

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

-- Seeds
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
```

---

## 8. INSTRUCCIONES FINALES PARA CLAUDE CODE

Cuando el usuario te diga "comencemos" o equivalente:

1. **Lee este documento completo si aún no lo has hecho.**
2. **Confirma con el usuario** los siguientes datos antes de empezar:
   - Nombre para el `LICENSE` (MIT).
   - Si quiere que el dashboard sea Next.js o prefiere Metabase (más rápido pero menos custom).
   - Si tiene preferencia sobre nombres de variables de entorno.
3. **Etapa 1**: Invoca `fortunia-scaffolder` con el brief de la sección 3.1. Espera "ok continúa".
4. **Etapa 2**: Invoca `fortunia-docker`. Espera "ok continúa".
5. ... y así sucesivamente, una etapa a la vez.
6. **Al final de cada etapa**, ejecuta los criterios de validación, reporta resultado, y espera confirmación antes de avanzar.
7. **Si un sub-agente falla o produce algo subóptimo**, NO insistas hasta cinco veces. Reporta al usuario, pide guía, considera escalar a Sonnet (si era Haiku) o a Opus (si era Sonnet).
8. **Al terminar todas las etapas**, ejecuta el checklist de "Criterios de Completitud" de la sección 7 y reporta.

---

**Fin del plan maestro.**

Última revisión: este documento asume Claude Code v2.x, Sonnet 4.6 y Haiku 4.5 vigentes, y OpenClaw self-hosted en macOS Apple Silicon con `sandbox-mode: "off"`. Si el usuario actualiza alguno de estos componentes, revisar compatibilidad antes de re-ejecutar.
