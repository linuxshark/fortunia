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
