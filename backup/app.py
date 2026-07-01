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
