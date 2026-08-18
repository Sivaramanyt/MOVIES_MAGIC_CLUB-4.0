from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: SecretStr
    webhook_base_url: str
    webhook_path: str = "/telegram/webhook"
    webhook_secret: str
    database_url: str
    tmdb_api_key: SecretStr
    admin_user_ids: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: SecretStr = SecretStr("")
    reindex_session_string: SecretStr = SecretStr("")
    reindex_channel_id: int | None = None
    reindex_max_messages: int = 10000
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Ensure SQLAlchemy uses the asyncpg PostgreSQL driver."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"

    @property
    def reindex_configured(self) -> bool:
        return (
            self.telegram_api_id > 0
            and bool(self.telegram_api_hash.get_secret_value())
            and bool(self.reindex_session_string.get_secret_value())
            and self.reindex_channel_id is not None
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
