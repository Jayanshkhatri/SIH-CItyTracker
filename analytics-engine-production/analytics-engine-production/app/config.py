"""Application configuration.

Settings can be supplied through environment variables or a .env file.
For PostgreSQL/Supabase, DB_* fields are supported so passwords containing
URL-special characters do not need manual URL encoding.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # Authentication. Empty string => dev mode (auth disabled, with a warning).
    analytics_api_key: str = ""

    # Comma-separated browser origins allowed to call the API. Empty = no CORS middleware.
    cors_origins: str = ""

    # Backward-compatible SQLite / DATABASE_URL fallback.
    database_url: str = "sqlite:///./anpr_analytics.db"

    # PostgreSQL / Supabase connection fields.
    db_name: str = ""
    db_user: str = ""
    db_password: str = ""
    db_host: str = ""
    db_port: int = 5432

    # Traffic-density thresholds (vehicle counts per camera per window).
    density_low_threshold: int = 10
    density_high_threshold: int = 30

    # Congestion: camera is CONGESTED when current/baseline >= this ratio.
    congestion_threshold: float = 1.5

    # Default size (minutes) of one bucket in the trends endpoint.
    default_bucket_minutes: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def use_postgres(self) -> bool:
        """Use DB_* settings when a PostgreSQL host is configured."""
        return bool(self.db_host.strip() and self.db_user.strip() and self.db_name.strip())

    @property
    def resolved_database_url(self) -> str | URL:
        """Return a safely constructed PostgreSQL URL or the SQLite fallback."""
        if self.use_postgres:
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
            )
        return self.database_url

    @property
    def is_sqlite(self) -> bool:
        """Whether the active database configuration is SQLite."""
        return not self.use_postgres and self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return a single shared settings object (cached)."""
    return Settings()
