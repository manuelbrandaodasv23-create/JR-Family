from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./jr_family.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_url(cls, value: str) -> str:
        # Cloud providers supply PostgreSQL URLs without a driver name.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    jwt_secret: str = "dev-only-change-me-please-use-32-bytes-minimum"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    invite_minutes: int = 15
    cors_origins: str = "*"
    low_battery_percent: int = 15
    history_retention_days: int = 30
    firebase_enabled: bool = False
    firebase_credentials_path: str | None = None
    firebase_project_id: str | None = None
    admin_panel_enabled: bool = True
    environment: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
if settings.environment == "production":
    if len(settings.jwt_secret) < 32 or settings.jwt_secret.startswith(("dev-", "change-", "REPLACE_")):
        raise RuntimeError("JWT_SECRET forte com pelo menos 32 caracteres é obrigatório")
    if settings.cors_origins == "*" or not settings.database_url.startswith("postgresql"):
        raise RuntimeError("Produção exige PostgreSQL e CORS explícito")
