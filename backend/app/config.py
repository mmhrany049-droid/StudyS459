"""Central application settings (Phase 0: foundation only, no business logic).

All settings come from environment variables (optionally via a local `.env`
file). See `.env.example`.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SS459 Study System"
    APP_VERSION: str = "1.0.0"
    # dev | test | prod
    ENV: str = "dev"
    DEBUG: bool = False

    # SQLite by default; postgres via e.g. postgresql+psycopg://...
    DATABASE_URL: str = "sqlite:///./ss459.db"

    # Spec 13: user-facing time is always Asia/Tehran.
    TIMEZONE: str = "Asia/Tehran"

    LOG_LEVEL: str = "INFO"
    # text | json
    LOG_FORMAT: str = "text"

    # Comma-separated list of allowed browser origins.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Single-user MVP: fixed user id. TEMPORARY scaffolding — the final auth
    # method is an open decision (spec 18, #9) and must stay simple.
    SINGLE_USER_ID: int = 1

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
