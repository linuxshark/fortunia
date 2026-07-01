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
