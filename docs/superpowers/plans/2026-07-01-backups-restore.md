# Backups automáticos al disco externo + restore web — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir backups automáticos diarios (DB + imágenes) al disco externo exFAT con rotación GFS, y un apartado web para restaurar backups con doble confirmación.

**Architecture:** Un servicio nuevo `backup/` (Python + FastAPI + `postgresql-client-16`), privilegiado (creds dueño) y **no publicado al host**, corre un scheduler diario y expone una API interna. El dashboard read-only gana una página `/admin` que es solo UI y llama a esa API por la red de compose. La DB sigue viva en el volumen Docker interno; solo los backups van al externo.

**Tech Stack:** FastAPI, Uvicorn, Pydantic Settings, psycopg 3, `pg_dump -Fc` / `pg_restore`, rsync, Jinja2 + HTMX (dashboard), Docker Compose.

## Global Constraints

- Python base image: `python:3.12-slim-bookworm` (igual que worker/dashboard).
- Cliente Postgres **versión 16** (el server es `postgres:16`; `pg_dump`/`pg_restore` deben ser ≥ server). Instalar vía repo PGDG.
- Config vía Pydantic Settings leyendo el `.env` del repo (`env_file`, `extra="ignore"`), patrón idéntico a `worker/config.py` y `dashboard/config.py`.
- El servicio `backup` **no expone puertos al host** (solo red compose). El dashboard lo alcanza en `http://backup:8000`.
- Ruta destino de backups en el host: `/Volumes/Workdir/Personal/fortunia-backups` (montada en el contenedor como `/backups`).
- Nombre de dump: `db-YYYYMMDD-HHMMSS.dump` (formato custom `-Fc`).
- Sentinel de disco montado: archivo `.fortunia-backup-volume` en la raíz del dir de backups; creado por un paso de setup explícito (nunca autocreado por el servicio).
- Imágenes: espejo único `images/` (append-only, inmutable por SHA256); nunca se borra ni versiona.
- Rotación GFS: 7 diarios + 4 semanales + 12 mensuales.
- Sin auth en `/admin`; barrera = doble confirmación (escribir `RESTAURAR`) + API no publicada al host.
- Tests del servicio backup: `cd backup && pytest -v` (patrón de `worker/tests`, con skip si no hay DB).
- Commits frecuentes (uno por tarea como mínimo). Mensajes en español, imperativo.

---

## File Structure

**Nuevo servicio `backup/`:**
- `backup/config.py` — Settings (dueño DB + parámetros de backup).
- `backup/storage.py` — guardia de disco montado (sentinel).
- `backup/rotation.py` — lógica pura GFS (selección/poda) y etiqueta de tier.
- `backup/engine.py` — `run_backup`, `list_backups`, `restore`, `validate_name` (subprocess a pg_dump/pg_restore/rsync).
- `backup/scheduler.py` — loop asíncrono que dispara el backup diario a `BACKUP_TIME`.
- `backup/app.py` — FastAPI: `/health`, `/backups`, `/backups/run`, `/restore`.
- `backup/requirements.txt`, `backup/Dockerfile`.
- `backup/tests/conftest.py`, `backup/tests/test_rotation.py`, `backup/tests/test_storage.py`, `backup/tests/test_engine.py`, `backup/tests/test_app.py`.

**Modificados:**
- `docker-compose.yml` — quitar `db-backup`, añadir `backup`.
- `.env.example` — parámetros nuevos.
- `dashboard/config.py` — `backup_url`.
- `dashboard/requirements.txt` — `httpx`.
- `dashboard/app.py` — rutas `/admin`, `/admin/backup`, `/admin/restore`.
- `dashboard/templates/admin.html` (nuevo), `dashboard/templates/base.html` (link nav).
- `Makefile` — `backup`, `backups`, `restore`, `backup-init`.
- `CLAUDE.md` — sección de backups/restore (prerrequisito File Sharing).

---

## Task 1: Scaffold del servicio `backup` (config + Docker)

**Files:**
- Create: `backup/config.py`
- Create: `backup/requirements.txt`
- Create: `backup/Dockerfile`
- Create: `backup/tests/conftest.py`
- Test: `backup/tests/test_config.py`

**Interfaces:**
- Produces: `backup.config.Settings` con campos `postgres_user/password/db/host/port`, `backup_dir: str`, `backup_time: str`, `backup_tz: str`, `backup_keep_daily/weekly/monthly: int`, `image_store: str`, `sentinel_name: str`; propiedades `dsn -> str`, `dsn_maintenance -> str` (db `postgres`), `backup_path -> Path`, `image_dir -> Path`, `pg_env() -> dict[str,str]`. Instancia módulo `settings`.

- [ ] **Step 1: Write the failing test**

```python
# backup/tests/test_config.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Settings  # noqa: E402


def test_defaults_and_dsn():
    s = Settings(
        postgres_user="boleta", postgres_password="pw", postgres_db="boletas",
        postgres_host="postgres", postgres_port=5432,
        backup_dir="/backups", backup_time="03:00", backup_tz="America/Santiago",
        image_store="/app/data/images",
    )
    assert s.dsn == "postgresql://boleta:pw@postgres:5432/boletas"
    assert s.dsn_maintenance.endswith("/postgres")
    assert s.backup_path == Path("/backups")
    assert s.backup_keep_daily == 7
    assert s.backup_keep_weekly == 4
    assert s.backup_keep_monthly == 12
    assert s.sentinel_name == ".fortunia-backup-volume"
    env = s.pg_env()
    assert env["PGPASSWORD"] == "pw" and env["PGHOST"] == "postgres"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_config.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'config'`.

- [ ] **Step 3: Write `backup/config.py`**

```python
"""Settings del servicio de backup. Lee el .env del repo (host) o env de compose.

Usa credenciales de DUEÑO de la DB (postgres_user/password) — este servicio es el
único con privilegios de escritura/restore; por eso NO se publica al host.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    postgres_user: str = "boleta"
    postgres_password: str = "change_me"
    postgres_db: str = "boletas"
    postgres_host: str = "localhost"     # 'postgres' dentro de compose
    postgres_port: int = 5432

    backup_dir: str = "/backups"                 # ruta dentro del contenedor
    backup_time: str = "03:00"                   # HH:MM local (backup_tz)
    backup_tz: str = "America/Santiago"
    backup_keep_daily: int = 7
    backup_keep_weekly: int = 4
    backup_keep_monthly: int = 12
    image_store: str = "/app/data/images"
    sentinel_name: str = ".fortunia-backup-volume"

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def dsn_maintenance(self) -> str:
        """DSN a la DB 'postgres' — para terminar conexiones sin estar dentro de boletas."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/postgres"
        )

    @property
    def backup_path(self) -> Path:
        return Path(self.backup_dir)

    @property
    def image_dir(self) -> Path:
        return Path(self.image_store)

    def pg_env(self) -> dict[str, str]:
        """Variables PG* para invocar pg_dump/pg_restore por subprocess."""
        return {
            "PGHOST": self.postgres_host,
            "PGPORT": str(self.postgres_port),
            "PGUSER": self.postgres_user,
            "PGPASSWORD": self.postgres_password,
            "PGDATABASE": self.postgres_db,
        }


settings = Settings()
```

- [ ] **Step 4: Create `backup/requirements.txt`**

```
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic-settings>=2.0
psycopg[binary]>=3.2
python-multipart>=0.0.9
```

- [ ] **Step 5: Create `backup/tests/conftest.py`**

```python
"""Fixtures del servicio backup. `db` conecta al dueño o skipea si no hay DB."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402
from config import settings  # noqa: E402


@pytest.fixture
def db():
    try:
        conn = psycopg.connect(settings.dsn, connect_timeout=2)
    except Exception:
        pytest.skip("DB no disponible — levanta con `make deploy` para tests DB")
    conn.autocommit = True
    yield conn
    conn.close()
```

- [ ] **Step 6: Create `backup/Dockerfile`**

```dockerfile
# Servicio de backup/restore. Necesita cliente Postgres 16 (>= server) y rsync.
FROM python:3.12-slim-bookworm

# Repo PGDG para postgresql-client-16 (bookworm trae 15, insuficiente para dump de 16)
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg rsync \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
         -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
         > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV IMAGE_STORE=/app/data/images
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backup/config.py backup/requirements.txt backup/Dockerfile backup/tests/
git commit -m "feat(backup): scaffold del servicio (config + Dockerfile + conftest)"
```

---

## Task 2: Guardia de disco montado (`storage.py`)

**Files:**
- Create: `backup/storage.py`
- Test: `backup/tests/test_storage.py`

**Interfaces:**
- Consumes: nada.
- Produces: `disk_available(backup_dir: Path, sentinel_name: str) -> bool`. `require_disk(backup_dir, sentinel_name) -> None` (lanza `DiskUnavailable` si falta). Excepción `DiskUnavailable(RuntimeError)`.

- [ ] **Step 1: Write the failing test**

```python
# backup/tests/test_storage.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import disk_available, require_disk, DiskUnavailable  # noqa: E402

SENTINEL = ".fortunia-backup-volume"


def test_available_when_sentinel_present(tmp_path):
    (tmp_path / SENTINEL).touch()
    assert disk_available(tmp_path, SENTINEL) is True


def test_unavailable_when_sentinel_missing(tmp_path):
    assert disk_available(tmp_path, SENTINEL) is False


def test_unavailable_when_dir_missing(tmp_path):
    assert disk_available(tmp_path / "nope", SENTINEL) is False


def test_require_disk_raises_when_missing(tmp_path):
    with pytest.raises(DiskUnavailable):
        require_disk(tmp_path, SENTINEL)


def test_require_disk_ok_when_present(tmp_path):
    (tmp_path / SENTINEL).touch()
    require_disk(tmp_path, SENTINEL)  # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_storage.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'storage'`.

- [ ] **Step 3: Write `backup/storage.py`**

```python
"""Guardia de disco montado.

Si el disco externo está desconectado, el mount point queda vacío y los escritos
irían silenciosamente a la capa efímera del contenedor. Un archivo centinela
(creado en el setup, nunca por el servicio) prueba que el disco real está montado.
"""
from pathlib import Path


class DiskUnavailable(RuntimeError):
    pass


def disk_available(backup_dir: Path, sentinel_name: str) -> bool:
    return (Path(backup_dir) / sentinel_name).exists()


def require_disk(backup_dir: Path, sentinel_name: str) -> None:
    if not disk_available(backup_dir, sentinel_name):
        raise DiskUnavailable(
            f"Disco de backups no disponible: falta el centinela "
            f"'{sentinel_name}' en {backup_dir}. ¿Está montado el disco externo "
            f"y ejecutaste 'make backup-init'?"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_storage.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backup/storage.py backup/tests/test_storage.py
git commit -m "feat(backup): guardia de disco montado (centinela)"
```

---

## Task 3: Lógica de rotación GFS (`rotation.py`)

**Files:**
- Create: `backup/rotation.py`
- Test: `backup/tests/test_rotation.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `parse_ts(filename: str) -> datetime | None` — parsea `db-YYYYMMDD-HHMMSS.dump`.
  - `select_keep(timestamps: list[datetime], keep_daily: int, keep_weekly: int, keep_monthly: int) -> set[datetime]`.
  - `plan_prune(filenames: list[str], keep_daily, keep_weekly, keep_monthly) -> list[str]` — nombres a borrar.
  - `tier_for(ts: datetime, now: datetime) -> str` — etiqueta de display: `"diario" | "semanal" | "mensual"`.

- [ ] **Step 1: Write the failing test**

```python
# backup/tests/test_rotation.py
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rotation import parse_ts, select_keep, plan_prune, tier_for  # noqa: E402


def test_parse_ts_ok():
    assert parse_ts("db-20260701-030000.dump") == datetime(2026, 7, 1, 3, 0, 0)


def test_parse_ts_bad_returns_none():
    assert parse_ts("images") is None
    assert parse_ts("db-nope.dump") is None


def test_keeps_last_n_daily():
    # 10 días consecutivos, 1 dump/día; con keep_daily=7 y 0 semanales/mensuales
    ts = [datetime(2026, 6, d, 3, 0, 0) for d in range(1, 11)]
    kept = select_keep(ts, keep_daily=7, keep_weekly=0, keep_monthly=0)
    assert kept == set(ts[-7:])          # los 7 más recientes


def test_multiple_per_day_keeps_latest_of_day():
    ts = [datetime(2026, 6, 1, 3, 0, 0), datetime(2026, 6, 1, 21, 0, 0)]
    kept = select_keep(ts, keep_daily=1, keep_weekly=0, keep_monthly=0)
    assert kept == {datetime(2026, 6, 1, 21, 0, 0)}   # el más tardío del día


def test_weekly_and_monthly_extend_retention():
    # un dump por día durante ~100 días -> con 7d/4w/12m se conservan más que 7
    base = datetime(2026, 1, 1, 3, 0, 0)
    ts = [base.replace() for _ in range(0)]
    from datetime import timedelta
    ts = [base + timedelta(days=i) for i in range(100)]
    kept = select_keep(ts, keep_daily=7, keep_weekly=4, keep_monthly=12)
    # 7 diarios + hasta 4 semanales + hasta 3-4 mensuales (100 días ~ 3 meses)
    assert len(kept) >= 7 + 3          # estrictamente más que solo diarios
    assert set(ts[-7:]).issubset(kept) # los 7 últimos siempre están


def test_plan_prune_returns_names_to_delete():
    names = [f"db-202606{d:02d}-030000.dump" for d in range(1, 11)]
    names.append("images")             # no es dump -> se ignora, nunca se borra
    to_delete = plan_prune(names, keep_daily=7, keep_weekly=0, keep_monthly=0)
    assert "images" not in to_delete
    assert set(to_delete) == {f"db-202606{d:02d}-030000.dump" for d in range(1, 4)}


def test_tier_for_labels():
    now = datetime(2026, 7, 1, 3, 0, 0)
    from datetime import timedelta
    assert tier_for(now - timedelta(days=2), now) == "diario"
    assert tier_for(now - timedelta(days=20), now) == "semanal"
    assert tier_for(now - timedelta(days=200), now) == "mensual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_rotation.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'rotation'`.

- [ ] **Step 3: Write `backup/rotation.py`**

```python
"""Rotación Grandfather-Father-Son sobre los dumps db-*.dump (lógica pura).

Cada dump cae en un bucket diario (fecha), semanal (año-semana ISO) y mensual
(año-mes). Se conserva el más reciente de cada uno de los últimos N buckets de
cada tipo; la unión es el conjunto a conservar. Todo lo demás se poda.
"""
from datetime import datetime, timedelta

_PREFIX = "db-"
_SUFFIX = ".dump"


def parse_ts(filename: str) -> datetime | None:
    if not (filename.startswith(_PREFIX) and filename.endswith(_SUFFIX)):
        return None
    core = filename[len(_PREFIX):-len(_SUFFIX)]      # YYYYMMDD-HHMMSS
    try:
        return datetime.strptime(core, "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def _keep_by_bucket(timestamps: list[datetime], keyfn, count: int) -> set[datetime]:
    if count <= 0:
        return set()
    newest: dict = {}
    for ts in timestamps:
        k = keyfn(ts)
        if k not in newest or ts > newest[k]:
            newest[k] = ts
    top_keys = sorted(newest, reverse=True)[:count]
    return {newest[k] for k in top_keys}


def select_keep(timestamps: list[datetime], keep_daily: int,
                keep_weekly: int, keep_monthly: int) -> set[datetime]:
    daily = _keep_by_bucket(timestamps, lambda t: t.date(), keep_daily)
    weekly = _keep_by_bucket(timestamps, lambda t: t.isocalendar()[:2], keep_weekly)
    monthly = _keep_by_bucket(timestamps, lambda t: (t.year, t.month), keep_monthly)
    return daily | weekly | monthly


def plan_prune(filenames: list[str], keep_daily: int,
               keep_weekly: int, keep_monthly: int) -> list[str]:
    dated = [(f, parse_ts(f)) for f in filenames]
    dumps = [(f, ts) for f, ts in dated if ts is not None]
    keep = select_keep([ts for _, ts in dumps], keep_daily, keep_weekly, keep_monthly)
    return [f for f, ts in dumps if ts not in keep]


def tier_for(ts: datetime, now: datetime) -> str:
    """Etiqueta de display (aproximada, no afecta la poda)."""
    age = now - ts
    if age <= timedelta(days=7):
        return "diario"
    if age <= timedelta(weeks=5):
        return "semanal"
    return "mensual"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_rotation.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add backup/rotation.py backup/tests/test_rotation.py
git commit -m "feat(backup): rotación GFS (lógica pura + tests)"
```

---

## Task 4: Motor de backup (`engine.py` — run_backup + list_backups)

**Files:**
- Create: `backup/engine.py`
- Test: `backup/tests/test_engine.py`

**Interfaces:**
- Consumes: `config.settings`, `storage.require_disk`, `rotation.parse_ts/plan_prune/tier_for`.
- Produces:
  - `run_backup(settings) -> dict` — hace `pg_dump -Fc`, rsync de imágenes al espejo, poda GFS. Devuelve `{"file": str, "size": int, "ts": iso}`. Lanza `DiskUnavailable` si el disco no está.
  - `list_backups(settings) -> list[dict]` — `[{"name","size","ts","tier"}]` orden desc por fecha.
  - `_run(cmd: list[str], env: dict) -> None` — helper subprocess (lanza en error).

- [ ] **Step 1: Write the failing test**

```python
# backup/tests/test_engine.py
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine  # noqa: E402
from config import Settings  # noqa: E402
from storage import DiskUnavailable  # noqa: E402


def _settings(tmp_path, images) -> Settings:
    return Settings(
        postgres_host="localhost", postgres_port=5432,
        postgres_user="boleta", postgres_password="change_me", postgres_db="boletas",
        backup_dir=str(tmp_path), image_store=str(images),
    )


def test_run_backup_raises_without_sentinel(tmp_path):
    s = _settings(tmp_path, tmp_path / "img")
    with pytest.raises(DiskUnavailable):
        engine.run_backup(s)


def test_list_backups_reads_dir(tmp_path):
    (tmp_path / "db-20260601-030000.dump").write_bytes(b"x" * 10)
    (tmp_path / "db-20260701-030000.dump").write_bytes(b"y" * 20)
    (tmp_path / "images").mkdir()
    s = _settings(tmp_path, tmp_path / "images")
    rows = engine.list_backups(s)
    assert [r["name"] for r in rows] == ["db-20260701-030000.dump", "db-20260601-030000.dump"]
    assert rows[0]["size"] == 20
    assert rows[0]["tier"] in {"diario", "semanal", "mensual"}


@pytest.mark.usefixtures("db")
def test_run_backup_creates_dump_and_syncs_images(tmp_path, db):
    images = tmp_path / "src_images"
    images.mkdir()
    (images / "abc123.bin").write_bytes(b"fake-jpeg")
    (tmp_path / ".fortunia-backup-volume").touch()      # sentinel presente
    s = _settings(tmp_path, images)
    out = engine.run_backup(s)
    dump = tmp_path / out["file"]
    assert dump.exists() and dump.stat().st_size > 0
    assert (tmp_path / "images" / "abc123.bin").read_bytes() == b"fake-jpeg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_engine.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'engine'` (el test de DB se skipea si no hay Postgres).

- [ ] **Step 3: Write `backup/engine.py` (parte 1: run_backup + list_backups)**

```python
"""Motor de backup/restore: subprocess a pg_dump/pg_restore/rsync + rotación."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

import psycopg

from config import Settings
from storage import require_disk
from rotation import parse_ts, plan_prune, tier_for

_MIRROR = "images"


def _run(cmd: list[str], env: dict[str, str]) -> None:
    full_env = {**os.environ, **env}
    proc = subprocess.run(cmd, env=full_env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} falló ({proc.returncode}): {proc.stderr.strip()}")


def run_backup(settings: Settings) -> dict:
    require_disk(settings.backup_path, settings.sentinel_name)
    ts = datetime.now()
    name = f"db-{ts:%Y%m%d-%H%M%S}.dump"
    dump_path = settings.backup_path / name

    # 1) DB → formato custom comprimido
    _run(["pg_dump", "-Fc", "-f", str(dump_path)], settings.pg_env())

    # 2) Imágenes → espejo append-only (sin --delete: nunca se borran imágenes)
    mirror = settings.backup_path / _MIRROR
    mirror.mkdir(parents=True, exist_ok=True)
    if settings.image_dir.exists():
        _run(["rsync", "-a", f"{settings.image_dir}/", f"{mirror}/"], {})

    # 3) Poda GFS
    names = [p.name for p in settings.backup_path.glob("db-*.dump")]
    for victim in plan_prune(names, settings.backup_keep_daily,
                             settings.backup_keep_weekly, settings.backup_keep_monthly):
        (settings.backup_path / victim).unlink(missing_ok=True)

    return {"file": name, "size": dump_path.stat().st_size, "ts": ts.isoformat()}


def list_backups(settings: Settings) -> list[dict]:
    now = datetime.now()
    rows = []
    for p in settings.backup_path.glob("db-*.dump"):
        ts = parse_ts(p.name)
        if ts is None:
            continue
        rows.append({
            "name": p.name,
            "size": p.stat().st_size,
            "ts": ts.isoformat(),
            "tier": tier_for(ts, now),
        })
    rows.sort(key=lambda r: r["ts"], reverse=True)
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_engine.py -v`
Expected: PASS los tests sin DB; el de DB pasa si `make deploy` está arriba, o `skip` si no.

- [ ] **Step 5: Commit**

```bash
git add backup/engine.py backup/tests/test_engine.py
git commit -m "feat(backup): motor de backup (pg_dump + espejo imágenes + poda GFS)"
```

---

## Task 5: Motor de restore (`engine.py` — validate_name + restore)

**Files:**
- Modify: `backup/engine.py`
- Test: `backup/tests/test_engine.py` (añadir casos)

**Interfaces:**
- Consumes: `config.settings`, `psycopg`.
- Produces:
  - `validate_name(settings, name: str) -> Path` — acepta solo un `db-*.dump` existente dentro de `backup_path`; lanza `ValueError` ante traversal/inexistente.
  - `restore(settings, name: str) -> dict` — termina conexiones ajenas a la DB, `pg_restore --clean --if-exists --no-owner`, rsync espejo→local. Devuelve `{"restored": name}`.

- [ ] **Step 1: Write the failing test (añadir al final de test_engine.py)**

```python
def test_validate_name_rejects_traversal(tmp_path):
    (tmp_path / "db-20260701-030000.dump").write_bytes(b"x")
    s = _settings(tmp_path, tmp_path / "img")
    with pytest.raises(ValueError):
        engine.validate_name(s, "../../etc/passwd")
    with pytest.raises(ValueError):
        engine.validate_name(s, "db-does-not-exist.dump")
    with pytest.raises(ValueError):
        engine.validate_name(s, "notadump.txt")


def test_validate_name_accepts_existing(tmp_path):
    (tmp_path / "db-20260701-030000.dump").write_bytes(b"x")
    s = _settings(tmp_path, tmp_path / "img")
    p = engine.validate_name(s, "db-20260701-030000.dump")
    assert p == tmp_path / "db-20260701-030000.dump"


@pytest.mark.usefixtures("db")
def test_backup_then_restore_roundtrip(tmp_path, db):
    images = tmp_path / "src_images"
    images.mkdir()
    (tmp_path / ".fortunia-backup-volume").touch()
    s = _settings(tmp_path, images)
    # marcador temporal en una tabla que existe siempre
    with db.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS _bak_probe (v int);")
        cur.execute("INSERT INTO _bak_probe VALUES (42);")
    out = engine.run_backup(s)
    with db.cursor() as cur:
        cur.execute("DELETE FROM _bak_probe;")
    engine.restore(s, out["file"])
    with db.cursor() as cur:
        cur.execute("SELECT v FROM _bak_probe;")
        assert cur.fetchone()[0] == 42
        cur.execute("DROP TABLE _bak_probe;")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_engine.py -k "validate_name or roundtrip" -v`
Expected: FAIL con `AttributeError: module 'engine' has no attribute 'validate_name'`.

- [ ] **Step 3: Extend `backup/engine.py` (añadir imports y funciones)**

Añadir al final del archivo:

```python
def validate_name(settings: Settings, name: str) -> Path:
    if parse_ts(name) is None:                      # solo db-YYYYMMDD-HHMMSS.dump
        raise ValueError(f"Nombre de backup inválido: {name!r}")
    path = (settings.backup_path / name).resolve()
    if path.parent != settings.backup_path.resolve():   # anti path-traversal
        raise ValueError(f"Ruta fuera del dir de backups: {name!r}")
    if not path.exists():
        raise ValueError(f"El backup no existe: {name!r}")
    return path


def _terminate_connections(settings: Settings) -> None:
    with psycopg.connect(settings.dsn_maintenance, autocommit=True) as conn:
        conn.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (settings.postgres_db,),
        )


def restore(settings: Settings, name: str) -> dict:
    require_disk(settings.backup_path, settings.sentinel_name)
    dump = validate_name(settings, name)

    # 1) soltar conexiones ajenas para evitar contención de locks en el DROP
    _terminate_connections(settings)

    # 2) restaurar objetos (drop + recreate)
    _run(["pg_restore", "--clean", "--if-exists", "--no-owner",
          "-d", settings.postgres_db, str(dump)], settings.pg_env())

    # 3) rellenar imágenes desde el espejo (sin --delete: no toca locales extra)
    mirror = settings.backup_path / _MIRROR
    if mirror.exists():
        settings.image_dir.mkdir(parents=True, exist_ok=True)
        _run(["rsync", "-a", f"{mirror}/", f"{settings.image_dir}/"], {})

    return {"restored": name}
```

> Nota: `pg_restore --clean` puede emitir warnings a stderr sobre objetos inexistentes incluso con `--if-exists`; si eso hiciera fallar `_run`, usar `--exit-on-error` NO, y en su lugar tolerar returncode de warnings. En la práctica `--if-exists` evita el error; si aparece un falso fallo, ajustar `_run` para restore con un flag `tolerate_warnings`. Mantener simple hasta que el test roundtrip lo exija.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_engine.py -v`
Expected: PASS (los de DB requieren `make deploy`; si no, skip).

- [ ] **Step 5: Commit**

```bash
git add backup/engine.py backup/tests/test_engine.py
git commit -m "feat(backup): restore (validación anti-traversal + pg_restore + imágenes)"
```

---

## Task 6: API FastAPI + scheduler (`app.py`, `scheduler.py`)

**Files:**
- Create: `backup/scheduler.py`
- Create: `backup/app.py`
- Test: `backup/tests/test_app.py`

**Interfaces:**
- Consumes: `engine.run_backup/list_backups/restore`, `storage.disk_available`, `config.settings`.
- Produces (HTTP): `GET /health`, `GET /backups`, `POST /backups/run`, `POST /restore` (form `name`).
- Produces (scheduler): `next_run_at(now, hh, mm, tz) -> datetime`, `run_scheduler(settings, stop_event)`.

- [ ] **Step 1: Write the failing test**

```python
# backup/tests/test_app.py
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod           # noqa: E402
from scheduler import next_run_at  # noqa: E402


def test_next_run_at_today_and_tomorrow():
    tz = ZoneInfo("America/Santiago")
    now = datetime(2026, 7, 1, 1, 0, tzinfo=tz)     # antes de 03:00
    assert next_run_at(now, 3, 0, tz) == datetime(2026, 7, 1, 3, 0, tzinfo=tz)
    now2 = datetime(2026, 7, 1, 5, 0, tzinfo=tz)    # después de 03:00
    assert next_run_at(now2, 3, 0, tz) == datetime(2026, 7, 2, 3, 0, tzinfo=tz)


def test_health_and_backups_endpoints(monkeypatch):
    monkeypatch.setattr(appmod.engine, "list_backups", lambda s: [{"name": "db-x.dump"}])
    monkeypatch.setattr(appmod, "disk_available", lambda d, n: True)
    client = TestClient(appmod.app)
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["disk_ok"] is True
    r = client.get("/backups")
    assert r.json() == [{"name": "db-x.dump"}]


def test_run_and_restore_endpoints(monkeypatch):
    monkeypatch.setattr(appmod.engine, "run_backup", lambda s: {"file": "db-y.dump", "size": 1, "ts": "t"})
    monkeypatch.setattr(appmod.engine, "restore", lambda s, name: {"restored": name})
    client = TestClient(appmod.app)
    assert client.post("/backups/run").json()["file"] == "db-y.dump"
    assert client.post("/restore", data={"name": "db-y.dump"}).json()["restored"] == "db-y.dump"


def test_restore_bad_name_returns_400(monkeypatch):
    def boom(s, name): raise ValueError("nope")
    monkeypatch.setattr(appmod.engine, "restore", boom)
    client = TestClient(appmod.app)
    assert client.post("/restore", data={"name": "../evil"}).status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backup && python -m pytest tests/test_app.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write `backup/scheduler.py`**

```python
"""Scheduler diario: dispara run_backup a BACKUP_TIME (robusto a reinicios)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import engine
from config import Settings

log = logging.getLogger("backup.scheduler")


def next_run_at(now: datetime, hh: int, mm: int, tz: ZoneInfo) -> datetime:
    target = now.astimezone(tz).replace(hour=hh, minute=mm, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


async def run_scheduler(settings: Settings, stop: asyncio.Event) -> None:
    tz = ZoneInfo(settings.backup_tz)
    hh, mm = (int(x) for x in settings.backup_time.split(":"))
    while not stop.is_set():
        now = datetime.now(tz)
        wait = (next_run_at(now, hh, mm, tz) - now).total_seconds()
        try:
            await asyncio.wait_for(stop.wait(), timeout=wait)
            return                      # stop pedido
        except asyncio.TimeoutError:
            pass                        # llegó la hora
        try:
            result = engine.run_backup(settings)
            log.info("backup ok: %s", result)
        except Exception as exc:        # disco ausente u otro error: log y sigue
            log.warning("backup falló: %s", exc)
```

- [ ] **Step 4: Write `backup/app.py`**

```python
"""API interna del servicio backup (no publicada al host).

El dashboard read-only la consume por la red de compose (http://backup:8000).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, Form, HTTPException

import engine
from config import settings
from scheduler import run_scheduler
from storage import disk_available

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="fortunia-backup", version="1.0.0")
_stop = asyncio.Event()


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(run_scheduler(settings, _stop))


@app.on_event("shutdown")
async def _shutdown() -> None:
    _stop.set()


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "disk_ok": disk_available(settings.backup_path, settings.sentinel_name),
    }


@app.get("/backups")
def backups() -> list[dict]:
    return engine.list_backups(settings)


@app.post("/backups/run")
def run_now() -> dict:
    try:
        return engine.run_backup(settings)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/restore")
def restore(name: str = Form(...)) -> dict:
    try:
        return engine.restore(settings, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backup && python -m pytest tests/test_app.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add backup/scheduler.py backup/app.py backup/tests/test_app.py
git commit -m "feat(backup): API FastAPI + scheduler diario"
```

---

## Task 7: Wiring de compose, .env, sentinel bootstrap y Makefile

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `Makefile`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: servicio `backup` (Task 1-6).
- Produces: servicio compose `backup`; `.env` vars; targets `make backup`, `make backups`, `make restore FILE=`, `make backup-init`.

- [ ] **Step 1: Reemplazar el servicio `db-backup` en `docker-compose.yml`**

Borrar el bloque completo `db-backup:` (el `while true; sleep 86400` …) y añadir:

```yaml
  backup:
    build: ./backup
    restart: unless-stopped
    env_file: .env
    environment:
      POSTGRES_HOST: postgres        # red de compose
      BACKUP_DIR: /backups           # ruta interna; el host la monta al disco externo
      IMAGE_STORE: /app/data/images
    volumes:
      - ${BACKUP_DIR:-./backups}:/backups
      - ./data/images:/app/data/images        # rw: respaldar y restaurar imágenes
    # SIN 'ports': servicio privilegiado, solo alcanzable por la red de compose
    depends_on:
      postgres:
        condition: service_healthy
```

- [ ] **Step 2: Añadir vars a `.env.example`**

Añadir al final:

```
# --- Backups automáticos al disco externo + restore web ---
# Ruta EN EL HOST donde se guardan los backups (disco externo exFAT).
# Debe estar en Docker Desktop → Settings → Resources → File Sharing.
BACKUP_DIR=/Volumes/Workdir/Personal/fortunia-backups
BACKUP_TIME=03:00
BACKUP_TZ=America/Santiago
BACKUP_KEEP_DAILY=7
BACKUP_KEEP_WEEKLY=4
BACKUP_KEEP_MONTHLY=12
# El dashboard llama a la API interna del servicio backup:
BACKUP_URL=http://backup:8000
```

- [ ] **Step 3: Reemplazar/añadir targets en `Makefile`**

Reemplazar el target `backup` actual por:

```makefile
## backup-init: crea el centinela en el disco externo (prueba que está montado)
.PHONY: backup-init
backup-init:
	@set -a; . ./.env; set +a; \
	if [ ! -d "$$BACKUP_DIR" ]; then \
		echo "✗ $$BACKUP_DIR no existe. ¿Está montado el disco externo?"; exit 1; \
	fi; \
	touch "$$BACKUP_DIR/.fortunia-backup-volume"; \
	echo "✓ Centinela creado en $$BACKUP_DIR"

## backup: fuerza un backup ahora (vía API del servicio backup)
.PHONY: backup
backup:
	$(COMPOSE) exec -T backup curl -sf -X POST http://localhost:8000/backups/run \
		| python3 -m json.tool

## backups: lista los backups disponibles
.PHONY: backups
backups:
	$(COMPOSE) exec -T backup curl -sf http://localhost:8000/backups \
		| python3 -m json.tool

## restore: restaura un backup  →  make restore FILE=db-YYYYMMDD-HHMMSS.dump
.PHONY: restore
restore:
	@[ -n "$(FILE)" ] || (echo "Uso: make restore FILE=db-YYYYMMDD-HHMMSS.dump" && exit 1)
	@read -p "⚠️  Restaurar '$(FILE)' SOBRESCRIBE la DB actual. Escribe 'RESTAURAR': " ans && [ "$$ans" = "RESTAURAR" ]
	$(COMPOSE) exec -T backup curl -sf -X POST http://localhost:8000/restore \
		-d "name=$(FILE)" | python3 -m json.tool
```

- [ ] **Step 4: Documentar en `CLAUDE.md`**

Añadir bajo "Database Access" una subsección:

```markdown
### Backups & Restore (disco externo)

Los backups (DB `pg_dump -Fc` + espejo de imágenes) se guardan en el disco externo
en `BACKUP_DIR` (ver `.env`). Prerrequisito: Docker Desktop → Settings → Resources →
File Sharing debe incluir `/Volumes/Workdir`.

```bash
make backup-init      # una vez: crea el centinela que prueba que el disco está montado
make backup           # fuerza un backup ahora
make backups          # lista backups disponibles
make restore FILE=db-YYYYMMDD-HHMMSS.dump   # restaura (pide confirmación)
```

Backup automático: diario a `BACKUP_TIME`. Rotación GFS (7 diarios/4 semanales/12
mensuales). Restore también disponible desde la web en `/admin`.
```

- [ ] **Step 5: Verificación manual**

```bash
docker compose config >/dev/null && echo "compose OK"     # valida YAML + interpolación
make backup-init                                           # crea el centinela
make deploy                                                # levanta backup incluido
make status                                                # 'backup' Up; 'db-backup' ya no existe
make backup                                                # {"file":"db-...dump", ...}
make backups                                               # lista con el nuevo dump
ls -la /Volumes/Workdir/Personal/fortunia-backups/         # dump + images/ presentes
```
Expected: el dump aparece en el disco externo; `make backups` lo lista.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .env.example Makefile CLAUDE.md
git commit -m "feat(backup): wiring compose + env + sentinel bootstrap + Makefile"
```

---

## Task 8: Página `/admin` en el dashboard

**Files:**
- Modify: `dashboard/config.py`
- Modify: `dashboard/requirements.txt`
- Modify: `dashboard/app.py`
- Create: `dashboard/templates/admin.html`
- Modify: `dashboard/templates/base.html:104`
- Test: `dashboard/tests/test_admin.py` (crear dir de tests si no existe)

**Interfaces:**
- Consumes: API del servicio backup (`GET /backups`, `POST /backups/run`, `POST /restore`) vía `settings.backup_url`.
- Produces (HTTP dashboard): `GET /admin`, `POST /admin/backup`, `POST /admin/restore` (form `name`, `confirm`).

- [ ] **Step 1: Añadir `backup_url` a `dashboard/config.py`**

Añadir dentro de `class Settings`, junto a los otros campos:

```python
    backup_url: str = "http://backup:8000"   # API interna del servicio backup
```

- [ ] **Step 2: Añadir `httpx` a `dashboard/requirements.txt`**

Añadir una línea:

```
httpx>=0.27
```

- [ ] **Step 3: Write the failing test**

```python
# dashboard/tests/test_admin.py
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as appmod  # noqa: E402


class _FakeResp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p


def test_admin_page_lists_backups(monkeypatch):
    monkeypatch.setattr(appmod, "_backup_get", lambda path: [
        {"name": "db-20260701-030000.dump", "size": 1234, "ts": "2026-07-01T03:00:00", "tier": "diario"},
    ])
    monkeypatch.setattr(appmod, "_backup_health", lambda: {"disk_ok": True})
    client = TestClient(appmod.app)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "db-20260701-030000.dump" in r.text


def test_admin_restore_requires_confirm_word(monkeypatch):
    called = {}
    monkeypatch.setattr(appmod, "_backup_post", lambda path, data=None: called.setdefault("data", data) or {"restored": data["name"]})
    monkeypatch.setattr(appmod, "_backup_get", lambda path: [])
    monkeypatch.setattr(appmod, "_backup_health", lambda: {"disk_ok": True})
    client = TestClient(appmod.app)
    # confirm incorrecto -> no llama a la API, 400
    r = client.post("/admin/restore", data={"name": "db-x.dump", "confirm": "nope"})
    assert r.status_code == 400
    assert "data" not in called
    # confirm correcto -> llama
    r = client.post("/admin/restore", data={"name": "db-x.dump", "confirm": "RESTAURAR"})
    assert r.status_code == 200
    assert called["data"] == {"name": "db-x.dump"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd dashboard && python -m pytest tests/test_admin.py -v`
Expected: FAIL con `AttributeError: module 'app' has no attribute '_backup_get'`.

- [ ] **Step 5: Añadir helpers y rutas a `dashboard/app.py`**

Tras los imports existentes, añadir `import httpx` y helpers + rutas (antes de la ruta `/image/{sha}`):

```python
import httpx


def _backup_get(path: str):
    with httpx.Client(timeout=10) as c:
        r = c.get(f"{settings.backup_url}{path}")
        r.raise_for_status()
        return r.json()


def _backup_post(path: str, data: dict | None = None):
    with httpx.Client(timeout=300) as c:      # restore puede tardar
        r = c.post(f"{settings.backup_url}{path}", data=data or {})
        r.raise_for_status()
        return r.json()


def _backup_health() -> dict:
    try:
        return _backup_get("/health")
    except Exception:
        return {"disk_ok": False, "unreachable": True}


def _admin_ctx(request: Request, message: str | None = None) -> dict:
    try:
        rows = _backup_get("/backups")
    except Exception:
        rows = []
    return {
        "request": request,
        "backups": rows,
        "health": _backup_health(),
        "message": message,
    }


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse(request, "admin.html", _admin_ctx(request))


@app.post("/admin/backup", response_class=HTMLResponse)
def admin_backup(request: Request):
    try:
        out = _backup_post("/backups/run")
        msg = f"Backup creado: {out['file']}"
    except Exception as exc:
        msg = f"Error en backup: {exc}"
    return templates.TemplateResponse(request, "admin.html", _admin_ctx(request, msg))


@app.post("/admin/restore", response_class=HTMLResponse)
def admin_restore(request: Request, name: str = Form(...), confirm: str = Form(...)):
    if confirm != "RESTAURAR":
        return JSONResponse({"error": "confirmación inválida"}, status_code=400)
    try:
        _backup_post("/restore", data={"name": name})
        msg = f"Restaurado: {name}"
    except Exception as exc:
        msg = f"Error al restaurar: {exc}"
    return templates.TemplateResponse(request, "admin.html", _admin_ctx(request, msg))
```

- [ ] **Step 6: Create `dashboard/templates/admin.html`**

```html
{% extends "base.html" %}
{% block title %}fortunia · admin{% endblock %}
{% block content %}
<hgroup>
  <h2>Backups & Restauración</h2>
  <p class="muted">
    {% if health.disk_ok %}
      <span style="color:#16a34a">● Disco de backups montado</span>
    {% else %}
      <span style="color:#ef4444">● Disco no disponible{% if health.unreachable %} (servicio backup inalcanzable){% endif %}</span>
    {% endif %}
  </p>
</hgroup>

{% if message %}<article><small>{{ message }}</small></article>{% endif %}

<form method="post" action="/admin/backup">
  <button type="submit" {% if not health.disk_ok %}disabled{% endif %}>Backup ahora</button>
</form>

<table>
  <thead><tr><th>Backup</th><th>Fecha</th><th>Tier</th><th>Tamaño</th><th></th></tr></thead>
  <tbody>
    {% for b in backups %}
    <tr>
      <td><code>{{ b.name }}</code></td>
      <td>{{ b.ts }}</td>
      <td>{{ b.tier }}</td>
      <td>{{ (b.size / 1024) | round(1) }} KB</td>
      <td>
        <form method="post" action="/admin/restore" class="restore-form">
          <input type="hidden" name="name" value="{{ b.name }}">
          <input type="text" name="confirm" placeholder="escribe RESTAURAR" required
                 autocomplete="off" style="width:12rem;display:inline-block">
          <button type="submit" class="secondary"
                  onclick="return this.form.confirm.value==='RESTAURAR'">Restaurar</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="muted">No hay backups todavía.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 7: Añadir link en `dashboard/templates/base.html:104`**

Tras la línea de "Ingresos", añadir:

```html
      <li><a href="/admin">Admin</a></li>
```

- [ ] **Step 8: Run test to verify it passes**

Run: `cd dashboard && python -m pytest tests/test_admin.py -v`
Expected: PASS (2 passed).

- [ ] **Step 9: Verificación visual (con servicios arriba)**

```bash
make dashboard
open http://localhost:8001/admin      # lista backups, botón "Backup ahora", indicador de disco
```
Expected: la página carga, muestra el estado del disco y los backups.

- [ ] **Step 10: Commit**

```bash
git add dashboard/config.py dashboard/requirements.txt dashboard/app.py \
        dashboard/templates/admin.html dashboard/templates/base.html dashboard/tests/test_admin.py
git commit -m "feat(dashboard): página /admin de backups + restore con doble confirmación"
```

---

## Self-Review (completada por el autor del plan)

**Spec coverage:**
- DB viva en interno / backups al externo → Task 4/7 (montaje + engine). ✓
- exFAT no hospeda data dir → decisión respetada (solo backups). ✓
- Rotación GFS 7/4/12 → Task 3 + Task 4 (poda). ✓
- Restore completo con doble confirmación → Task 5 (engine) + Task 8 (UI `RESTAURAR`). ✓
- Diario + on-demand → Task 6 (scheduler) + Task 7 (`make backup`) + Task 8 (botón). ✓
- DB + imágenes → Task 4 (rsync espejo) + Task 5 (restore espejo). ✓
- Sin auth, solo confirmación → Task 8 (validación `confirm`) + API no publicada (Task 7). ✓
- Ruta `/Volumes/Workdir/Personal/fortunia-backups` → `.env.example` Task 7. ✓
- Servicio privilegiado aislado, no publicado → Task 7 (sin `ports`). ✓
- Guardia de disco montado (centinela) → Task 2 + Task 7 (`backup-init`). ✓
- Reemplaza `db-backup` → Task 7. ✓
- Prerrequisito File Sharing → Task 7 (CLAUDE.md + comentario .env). ✓
- Testing unit (GFS/guardia/validación) + integración (roundtrip) → Tasks 2,3,4,5. ✓

**Type consistency:** `settings.backup_path/image_dir/pg_env/dsn_maintenance/sentinel_name` definidos en Task 1 y usados consistentes en Tasks 2/4/5/6. `run_backup/list_backups/restore/validate_name` firmas idénticas entre engine (Task 4/5) y consumidores (Task 6). `_backup_get/_backup_post/_backup_health` definidos en Task 8 y mockeados en su test. ✓

**Placeholder scan:** sin TBD/TODO; todo el código está completo. La única nota condicional (warnings de `pg_restore`) está acotada y no bloquea. ✓
