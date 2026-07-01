# Backups automáticos al disco externo + restore desde la web

**Fecha:** 2026-07-01
**Estado:** Diseño aprobado, pendiente de plan de implementación

## Contexto y problema

Fortunia corre localmente en un Mac mini vía Docker Compose. La base de datos
Postgres persiste hoy en un volumen Docker con nombre (`pgdata`), dentro del disco
interno. El usuario quiere:

1. Que los datos vivan/respalden en un disco duro externo siempre conectado
   ("Workdir", montado en `/Volumes/Workdir`).
2. Backups automáticos con rotación, guardados en ese disco externo.
3. Poder **restaurar** un backup desde un apartado nuevo de la interfaz web.

### Hallazgo técnico decisivo: el disco externo es exFAT

`/Volumes/Workdir` está formateado en **exFAT**. Postgres **no puede correr su
directorio de datos vivo sobre exFAT**: exFAT no soporta permisos/propietario
POSIX, ni `fsync` confiable, ni symlinks/hardlinks. `initdb` falla o corrompe datos
silenciosamente. En Docker Desktop macOS el bind-mount pasa además por virtiofs,
lo que agrava el problema. exFAT **sí** es válido para guardar archivos de backup
normales (`.dump`, `.tar.gz`, imágenes).

**Conclusión:** la durabilidad se logra con **backups robustos y frecuentes al
disco externo + restore**, no reubicando el data dir vivo. La DB sigue viva en el
disco interno (APFS, vía volumen Docker); solo los backups van al externo.

## Decisiones (acordadas con el usuario)

| Tema | Decisión |
|------|----------|
| Data en disco externo | Solo backups (DB viva se queda en disco interno) |
| Tipo de backup | Rotación de fulls (GFS): 7 diarios + 4 semanales + 12 mensuales |
| Restore desde web | Restore completo con doble confirmación |
| Frecuencia | Diario (hora fija) + backup manual on-demand |
| Alcance | DB + imágenes de boletas |
| Auth de la sección admin | Sin auth; solo doble confirmación (escribir `RESTAURAR` + nombre) |
| Ruta destino | `/Volumes/Workdir/Personal/fortunia-backups` |

## Arquitectura

### Principio de seguridad

El restore es destructivo y requiere el rol dueño de la DB (`boleta`), no el rol
read-only (`fortunia_ro`) que usa el dashboard. Para **no romper el modelo
read-only existente**, las credenciales de dueño se aíslan en un servicio nuevo,
privilegiado y **no publicado al host**. El dashboard nunca las toca.

### Componentes

```
┌────────────┐   HTTP interno (red compose)   ┌─────────────────────┐
│ dashboard  │ ─────────────────────────────► │ backup (privilegiado)│
│ (read-only)│   GET /backups                 │  - scheduler diario  │
│  /admin UI │   POST /backups/run            │  - API FastAPI       │
└────────────┘   POST /restore                │  - creds dueño        │
      ▲                                        │  - monta disco externo│
      │ :8001 (host)                           │  - monta ./data/images│
   usuario LAN                                 └──────────┬───────────┘
                                                          │
                                    ┌─────────────────────┼─────────────────┐
                                    ▼                     ▼                 ▼
                              Postgres (compose)   /Volumes/Workdir/    ./data/images
                                                   Personal/            (bind mount rw)
                                                   fortunia-backups
```

#### 1. Servicio nuevo `backup/`

Directorio con `Dockerfile` (patrón igual a `worker/` y `dashboard/`): imagen
Python + `postgresql-client-16`. Reemplaza el servicio `db-backup` actual (el loop
`sleep 86400` frágil, que además escribe al disco interno).

Responsabilidades:

- **Scheduler**: ejecuta un backup diario a hora fija (`BACKUP_TIME`, ej. 03:00 en
  `BACKUP_TZ`). Implementación con un loop asíncrono que calcula el próximo disparo
  (robusto a reinicios; no acumula drift como `sleep 86400`).
- **API FastAPI** (puerto interno 8000, **sin mapeo a host**, solo red compose):
  - `GET  /health` — estado: último backup, disco montado sí/no.
  - `GET  /backups` — lista de backups (nombre, fecha, tamaño, tier).
  - `POST /backups/run` — dispara un backup ahora.
  - `POST /restore` — restaura un backup dado (con token de confirmación).
- Montajes:
  - Red compose → Postgres (con `PGUSER=boleta`, dueño).
  - `${BACKUP_DIR}:/backups` (rw) → disco externo.
  - `./data/images:/app/data/images` (rw) → para respaldar y restaurar imágenes.

#### 2. Página admin en el dashboard (`/admin`)

- Lista de backups (nombre, fecha, tamaño, tier) obtenida de la API del servicio
  `backup`.
- Botón **"Backup ahora"** → `POST /backups/run`.
- Por cada backup, botón **"Restaurar"** que abre un modal exigiendo escribir
  `RESTAURAR` + el nombre exacto del archivo antes de habilitar el submit.
- Indicador de estado: último backup OK/fallido y si el disco externo está montado.
- **La página admin solo llama a la API HTTP del servicio `backup`; no toca la DB.**
  No hay escalada de privilegios en el proceso read-only.

## Estrategia de backup

### Base de datos

`pg_dump -Fc` (formato custom, comprimido) → `db-<YYYYMMDD-HHMMSS>.dump`. El formato
custom habilita `pg_restore --clean --if-exists` (drop + recreate objeto por objeto).

### Imágenes

Un **espejo único** `images/` dentro de `${BACKUP_DIR}`, sincronizado (rsync) en
cada corrida. Fundamento: las imágenes son **inmutables y append-only** — el nombre
de archivo es el SHA256 del contenido y nunca se borran ni modifican (idempotencia
por hash en `worker/db.py`). Por tanto un espejo siempre-actual es consistente con
*cualquier* dump, incluso viejo: todo hash referenciado por la DB existirá en el
espejo (que es un superconjunto). Evita duplicar imágenes en cada backup.

### Rotación GFS

Sobre los archivos `db-*.dump`, tras cada corrida se poda con política
Grandfather-Father-Son:

- Conservar **todos** los de los últimos 7 días (diarios).
- De los más viejos, conservar **uno por semana** durante 4 semanas (semanales).
- De los aún más viejos, conservar **uno por mes** durante 12 meses (mensuales).
- Podar el resto.

La política se calcula parseando el timestamp del nombre de archivo; no se etiqueta
tier en el nombre (se deriva de la fecha). El espejo de imágenes no se rota (es
append-only, siempre el conjunto completo).

## Restore (flujo seguro)

Al invocar `POST /restore` con un backup válido y el token de confirmación:

1. **Validar nombre**: solo se acepta un archivo que exista dentro de `${BACKUP_DIR}`
   (rechazar path traversal / rutas absolutas / `..`).
2. **Terminar conexiones ajenas** a `boletas`:
   `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='boletas'
   AND pid <> pg_backend_pid();` (evita contención de locks en el DROP).
3. **Restaurar DB**: `pg_restore --clean --if-exists --no-owner -d boletas <dump>`.
4. **Restaurar imágenes**: rsync del espejo `images/` → `./data/images` (rellena las
   que falten; no borra locales).
5. Worker y dashboard reconectan automáticamente en el siguiente request (psycopg
   reconecta por request; contenedores con `restart: unless-stopped`). Downtime de
   segundos.

## Robustez del disco externo

- **Prerrequisito de setup**: Docker Desktop debe compartir `/Volumes/Workdir`
  (Settings → Resources → File Sharing). Documentar en README/CLAUDE.md.
- **Guardia de disco montado**: si el disco está desconectado, el mount point queda
  vacío y los escritos irían silenciosamente a la capa efímera del contenedor. Antes
  de cada operación de escritura se verifica un **archivo centinela** conocido en
  `${BACKUP_DIR}` (creado en el setup inicial). Si falta:
  - Backup: se **omite**, se registra y se marca estado "disco no disponible".
  - Restore: se **rechaza** con error claro.
  - Visible en `GET /health` del servicio backup y en la página `/admin`.

## Configuración (.env nuevos)

```
BACKUP_DIR=/Volumes/Workdir/Personal/fortunia-backups   # host path bind-mounted
BACKUP_TIME=03:00                                        # hora local del backup diario
BACKUP_TZ=America/Santiago
BACKUP_KEEP_DAILY=7
BACKUP_KEEP_WEEKLY=4
BACKUP_KEEP_MONTHLY=12
BACKUP_URL=http://backup:8000                            # dashboard → API interna
```

Se añaden a `.env.example`. El servicio `backup` lee su config con Pydantic Settings
(patrón `config.py` existente). El dashboard añade `backup_url` a su `config.py`.

## Cambios en docker-compose.yml

- **Eliminar** el servicio `db-backup` (bash loop).
- **Añadir** servicio `backup` (build `./backup`), con `env_file: .env`, montajes
  descritos, `depends_on: postgres (healthy)`, **sin `ports`** (no expuesto al host),
  `restart: unless-stopped`.
- El dashboard gana dependencia lógica del servicio `backup` (solo para la UI admin;
  si `backup` está caído, `/admin` muestra estado degradado, no rompe el resto).

## Cambios en Makefile

- `make backup` → llama `POST /backups/run` de la API (on-demand) en vez del
  `pg_dump` inline.
- `make backups` → lista backups (`GET /backups`).
- `make restore FILE=<nombre>` → restore por CLI (misma API), con confirmación en
  terminal.
- El bloque de backup nocturno inline desaparece del compose.

## Testing

- **Unit**:
  - Política GFS: dado un conjunto de fechas de backups → verificar exactamente qué
    archivos se conservan y cuáles se podan (casos borde: <7 días, saltos de semana,
    cambio de mes/año).
  - Guardia de disco: centinela presente/ausente → permitir/omitir.
  - Validación de nombre de archivo (anti path-traversal).
- **Integración** (requiere DB de pruebas, patrón `worker/pytest`):
  - Backup real → archivo `.dump` creado y no vacío.
  - Restore: sembrar datos → backup → mutar/borrar → restore → verificar que las
    filas vuelven. Idealmente restaurando a una DB efímera para no tocar la de test
    principal, o usando una DB de test dedicada.

## Riesgos y trade-offs asumidos

- **Sin auth en `/admin`** (elección del usuario): cualquiera en la LAN que alcance
  `:8001` puede iniciar un restore. Mitigado por: (a) doble confirmación en la UI,
  (b) la API privilegiada del servicio `backup` **no está publicada al host** (solo
  red compose), (c) validación de nombre de archivo. Residual aceptado.
- **Downtime durante restore**: segundos, aceptable para uso personal.
- **Espejo de imágenes no versionado**: correcto porque las imágenes son
  inmutables/append-only; si esa invariante cambiara en el futuro, habría que
  revisar (versionar imágenes o incluirlas en el bundle por-backup).
- **exFAT**: no se pueden usar hardlinks para snapshots incrementales de imágenes;
  por eso el modelo de espejo único (que además es el correcto aquí).

## Fuera de alcance (YAGNI)

- PITR / WAL archiving (descartado: rotación de fulls es suficiente para esta DB).
- Backups incrementales de DB (Postgres 17 nativo; estamos en 16 y la DB es chica).
- Reubicar el data dir vivo al disco externo (inviable en exFAT).
- Autenticación/roles de usuario en el dashboard.
- Cifrado de backups.
- Arreglar el crash-loop de `pgadmin` (no relacionado; se anota como observación).
