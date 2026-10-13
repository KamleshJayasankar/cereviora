"""
CEREVIORA — Application Configuration

This module reads environment variables and provides typed settings
to the rest of the application.  Using a central config object means
you only need to change one place when deploying to different environments.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables or .env file."""

    # Database — defaults to a local SQLite file in the backend directory
    database_url: str = "sqlite:///./cereviora.db"

    # CORS origins the frontend is allowed to call from
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Application metadata
    app_name: str = "CEREVIORA"
    app_version: str = "0.1.0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Module-level singleton — import `settings` everywhere instead of re-creating
settings = Settings()
