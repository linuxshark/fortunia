"""Settings. Reads env vars (compose env_file) and, on host, the repo-root .env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    postgres_user: str = "boleta"
    postgres_password: str = "change_me"
    postgres_db: str = "boletas"
    postgres_host: str = "localhost"     # 'postgres' inside compose
    postgres_port: int = 5432

    ocr_host: str = "0.0.0.0"
    ocr_port: int = 8000
    image_store: str = "./data/images"   # absolute inside container (/app/data/images)
    tesseract_lang: str = "spa"
    gemini_api_key: str = ""             # si vacío, no se usa Gemini

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def image_dir(self) -> Path:
        p = Path(self.image_store)
        if not p.is_absolute():
            p = REPO_ROOT / p
        p = p.resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
