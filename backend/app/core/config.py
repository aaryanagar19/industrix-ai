from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_name: str = "INDUSTRIX AI"
    env: str = "development"
    # SQLite is the local fallback; set DATABASE_URL=postgresql+psycopg2://... for PostgreSQL
    database_url: str = f"sqlite:///{ROOT / 'industrix.db'}"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    models_dir: str = str(ROOT / "models")
    data_dir: str = str(ROOT / "data")
    storage_dir: str = str(ROOT / "storage")

    simulator_autostart: bool = True
    simulator_interval_seconds: float = 3.0

    allow_self_register: bool = True
    default_register_role: str = "plant_manager"
    max_upload_mb: int = 5
    login_rate_limit_per_minute: int = 30

    # Optional overrides for risk thresholds (otherwise learned thresholds from model metadata are used)
    risk_threshold_moderate: float | None = None
    risk_threshold_high: float | None = None
    risk_threshold_critical: float | None = None
    stale_reading_seconds: int = 120

    # Optional LLM summarisation (OpenAI-compatible). The platform works without it.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
