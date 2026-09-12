from functools import lru_cache
from typing import Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Validated runtime configuration with one database URL precedence rule."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "fastapi-service"
    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str | None = None
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @model_validator(mode="after")
    def validate_database_configuration(self) -> Self:
        if self.database_url:
            if not self.database_url.startswith("postgresql"):
                raise ValueError("DATABASE_URL must use a PostgreSQL URL")
            return self

        missing = [
            field
            for field, value in (
                ("POSTGRES_DB", self.postgres_db),
                ("POSTGRES_USER", self.postgres_user),
                ("POSTGRES_PASSWORD", self.postgres_password),
            )
            if value is None
        ]
        if missing:
            raise ValueError("Database configuration is missing: " + ", ".join(missing))
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """Return the injected URL or construct one from the base values."""
        if self.database_url:
            return self.database_url

        assert self.postgres_db is not None
        assert self.postgres_user is not None
        assert self.postgres_password is not None
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
