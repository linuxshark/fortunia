"""Settings del dashboard. Lee .env (compose env_file) y, en host, el .env del repo.

Usa campos PROPIOS (postgres_ro_user/password) para no chocar con el POSTGRES_USER
del worker que vive en el mismo .env. El dashboard conecta con un rol de SOLO LECTURA.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Rol de solo lectura (least privilege) — distinto del usuario del worker
    postgres_ro_user: str = "fortunia_ro"
    postgres_ro_password: str = "change_me_ro"
    postgres_db: str = "boletas"
    postgres_host: str = "localhost"     # 'postgres' dentro de compose
    postgres_port: int = 5432

    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000           # puerto interno; host lo publica en 8001
    image_store: str = "./data/images"   # absoluto dentro del container (/app/data/images)

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_ro_user}:{self.postgres_ro_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def image_dir(self) -> Path:
        p = Path(self.image_store)
        if not p.is_absolute():
            p = REPO_ROOT / p
        return p.resolve()


settings = Settings()
