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
