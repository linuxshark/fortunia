"""Motor de backup/restore: subprocess a pg_dump/pg_restore/rsync + rotación."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

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
