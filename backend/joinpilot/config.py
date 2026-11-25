"""Application settings.

Every tunable number and every secret is read here, from environment variables
or the `.env` file, so no threshold or key is hard-coded elsewhere.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed settings loaded from the environment (prefix-free) and `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Limits
    max_upload_mb: int = 50

    @property
    def projects_dir(self) -> Path:
        """Folder that holds one sub-folder (and one DuckDB file) per project."""
        return self.data_dir / "projects"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; tests clear the cache)."""
    return Settings()
