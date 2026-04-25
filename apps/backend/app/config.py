from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/kreator"
    app_env: str = "local"
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str = ""
    cors_origins: str = "*"


settings = Settings()
