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
