"""Application settings.

Every tunable number and every secret is read here, from environment variables
or the `.env` file, so no threshold or key is hard-coded elsewhere.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class SizeSpec(BaseModel):
    """Row counts for one dataset size (docs/data-model.md)."""

    customers: int
    products: int
    orders: int
    open_items: int


class IssueRates(BaseModel):
    """Share of rows affected by each planted data-quality issue."""

    orphan_order_items: float = Field(default=0.01, ge=0, le=1)
    orphan_open_items: float = Field(default=0.005, ge=0, le=1)
    duplicate_customers: float = Field(default=0.005, ge=0, le=0.5)
    null_key_open_items: float = Field(default=0.003, ge=0, le=1)
    stripped_zeros_open_items: float = Field(default=1.0, ge=0, le=1)


class SynthSettings(BaseModel):
    """Tunables for the synthetic ERP generator. Override with SYNTH__<NAME>."""

    sizes: dict[str, SizeSpec] = Field(
        default_factory=lambda: {
            "S": SizeSpec(customers=1_000, products=2_000, orders=10_000, open_items=8_000),
            "M": SizeSpec(customers=10_000, products=20_000, orders=100_000, open_items=80_000),
            "L": SizeSpec(customers=50_000, products=50_000, orders=500_000, open_items=400_000),
        }
    )
    order_start: date = date(2025, 1, 1)
    order_end: date = date(2026, 6, 30)
    open_item_start: date = date(2025, 7, 1)
    reference_date: date = date(2026, 6, 30)
    max_items_per_order: int = 5
    max_lines_per_document: int = 3
    eur_share: float = 0.10
    issues: IssueRates = Field(default_factory=IssueRates)


class ProfilingSettings(BaseModel):
    """Tunables for column statistics, candidate keys and overlap scores."""

    sample_values: int = 5
    max_pair_columns: int = 12
    overlap_sample_size: int = 10_000
    overlap_max_value_length: int = 40
    overlap_min_ratio: float = 0.1
    normalization_min_gain: float = 0.1


class Settings(BaseSettings):
    """Typed settings loaded from the environment (prefix-free) and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__", extra="ignore"
    )

    # App
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # Limits
    max_upload_mb: float = 50
    max_tables_per_project: int = 30
    max_columns_per_table: int = 200
    duckdb_memory_limit: str = "1GB"
    duckdb_threads: int = 2
    sample_sizes: list[str] = Field(default_factory=lambda: ["S", "M"])

    # Synthetic data generator
    synth: SynthSettings = Field(default_factory=SynthSettings)

    # Profiling
    profiling: ProfilingSettings = Field(default_factory=ProfilingSettings)

    @property
    def projects_dir(self) -> Path:
        """Folder that holds one sub-folder (and one DuckDB file) per project."""
        return self.data_dir / "projects"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; tests clear the cache)."""
    return Settings()
