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
