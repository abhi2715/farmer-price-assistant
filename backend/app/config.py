"""Application settings, loaded from environment variables (see /.env.example)."""
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore", protected_namespaces=("settings_",))

    env: str = "dev"
    # Postgres in Docker / Supabase in production; SQLite works for local dev/tests.
    database_url: str = f"sqlite:///{ROOT / 'agriroute.db'}"
    # Empty => in-memory fallbacks (cache, OTP store, rate limiter) and eager Celery.
    redis_url: str = ""

    jwt_secret: str = "dev-secret-change-me"
    jwt_ttl_hours: int = 24 * 7
    otp_dev_mode: bool = True  # OTP is always 123456 and returned in the API response
    otp_ttl_seconds: int = 300

    rate_limit_default: str = "300/minute"
    rate_limit_otp: str = "5/minute"
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    cors_origin_regex: str = ""  # e.g. https://farmer-price-assistant.*\.vercel\.app (preview + prod URLs)

    # Single-process hosting (Render free tier): run the bootstrap in a background thread at startup and
    # repeat it periodically, standing in for the Celery worker + beat.
    bootstrap_on_startup: bool = False
    bootstrap_interval_hours: float = 6

    # Data sources
    datagov_api_key: str = ""  # data.gov.in key for Agmarknet
    agmarknet_resource_id: str = "9ef84268-d588-465a-a308-a864a43d0070"
    use_live_apis: bool = False  # set true to pull Agmarknet/Open-Meteo in scheduled ingestion

    # ML
    model_dir: str = str(ROOT / "ml" / "artifacts")
    report_dir: str = str(ROOT / "ml" / "reports")
    mlflow_tracking_uri: str = ""  # e.g. http://mlflow:5000 ; empty => local ./mlruns
    enable_prophet: bool = True
    backtest_series: int = 24
    backtest_origins: int = 4
    lgbm_rounds: int = 400

    # Marketplace economics
    farmer_commission_pct: float = 0.5
    buyer_commission_pct: float = 1.5

    # Notifications (mocked unless a webhook is configured)
    sms_webhook_url: str = ""
    whatsapp_webhook_url: str = ""

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        # Accept the plain URLs Supabase/Render hand out (postgres://, postgresql://).
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
