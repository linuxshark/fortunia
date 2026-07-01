import sys
from datetime import datetime
from pathlib import Path

import psycopg
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
    # restore termina conexiones ajenas a la DB (incluida esta fixture) -> reconectar
    with psycopg.connect(s.dsn, autocommit=True) as conn2, conn2.cursor() as cur:
        cur.execute("SELECT v FROM _bak_probe;")
        assert cur.fetchone()[0] == 42
        cur.execute("DROP TABLE _bak_probe;")
