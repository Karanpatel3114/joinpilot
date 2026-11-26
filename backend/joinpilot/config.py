"""Application settings.

Every tunable number and every secret is read here, from environment variables
or the `.env` file, so no threshold or key is hard-coded elsewhere.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator
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
    overlap_max_columns: int = 300
    overlap_max_results: int = 5_000
    stats_batch_columns: int = 50
    normalization_min_gain: float = 0.1


class JoinSettings(BaseModel):
    """Tunables for join candidates and their scores (tuned on the dev split only)."""

    candidate_min_inclusion: float = 0.5
    unique_min: float = 0.999
    weight_inclusion: float = 0.35
    weight_name: float = 0.35
    weight_coverage: float = 0.15
    weight_key_strength: float = 0.15
    key_strength_full_at: int = Field(default=50, gt=1)
    name_fuzzy_weight: float = 0.5
    prefix_min_share: float = 0.8
    prefix_max_length: int = 4
    one_to_one_min_overlap: float = 0.95
    n_to_m_factor: float = 0.5
    accept_threshold: float = 0.7
    discriminator_max_distinct: int = 5
    discriminator_fill: float = 0.9
    preferred_filter_values: list[str] = Field(default_factory=lambda: ["E", "EN", "en"])


class LLMSettings(BaseModel):
    """Which model to call and how (D-005). The key itself is `GEMINI_API_KEY`."""

    provider: Literal["gemini", "fake"] = "gemini"
    model: str = "gemini-flash-lite-latest"
    temperature: float = 0.0
    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 30.0
    cache_responses: bool = True
    # USD per million (input, output) tokens at the paid list price, for cost estimates.
    # Free-tier calls are not billed; leave empty to report $0.
    prices_per_million: dict[str, tuple[float, float]] = Field(default_factory=dict)


class LimitSettings(BaseModel):
    """Request limits that keep a public demo and its free model quota healthy."""

    # Requests per minute from one client (IP address), for every endpoint but /health
    requests_per_minute: int = Field(default=240, ge=1)
    # Runs started plus questions asked (the calls that use the language model)
    expensive_per_minute: int = Field(default=6, ge=1)
    expensive_per_day: int = Field(default=60, ge=1)
    # The same, across all clients, so the free model quota cannot be spent by one visitor
    expensive_global_per_day: int = Field(default=300, ge=1)
    # Largest JSON request body in KB (uploads use MAX_UPLOAD_MB instead)
    max_body_kb: int = Field(default=512, ge=1)
    # Trusted proxies in front of the API; the client is the X-Forwarded-For entry they
    # added, counted from the right (1 on Render). 0 uses the connecting address.
    forwarded_hops: int = Field(default=0, ge=0, le=5)


class QASettings(BaseModel):
    """Plain-English questions answered with guarded, read-only SQL."""

    # Longest question accepted, in characters
    max_question_chars: int = Field(default=500, ge=10, le=5000)
    # Example values per column shown to the model
    example_values: int = Field(default=3, ge=0, le=10)
    # Model attempts per question: the first draft plus fixes after a guard refusal
    max_attempts: int = Field(default=2, ge=1, le=5)
    # Most rows an answer returns
    row_limit: int = Field(default=1000, ge=1, le=100_000)
    # Seconds a question's query may run before it is cancelled
    timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    # Longest text kept in one answer cell (longer text is cut with an ellipsis)
    max_cell_chars: int = Field(default=1000, ge=10, le=100_000)
    # Largest answer, in bytes of JSON; rows past it are left out and the answer is marked cut
    max_result_bytes: int = Field(default=2_000_000, ge=10_000, le=100_000_000)
    # Longest example value shown to the model, in characters
    example_max_chars: int = Field(default=40, ge=5, le=500)


class AgentSettings(BaseModel):
    """Tunables for the agent's ranking and its evidence checks."""

    prompt_example_values: int = 2
    ranking_max_candidates: int = 25
    rescue_min_score: float = 0.5
    explanation_tolerance_points: float = 0.6
    max_repairs: int = 2


class KPISettings(BaseModel):
    """Business rules for derived columns and metrics."""

    # As-of date for aging; empty means today. The sample data is as of 2026-06-30.
    reference_date: date | None = None
    # Upper bounds (days past due) of the aging buckets; the last bucket is open-ended
    aging_bucket_edges: list[int] = Field(default_factory=lambda: [30, 60, 90], min_length=1)
    # Rows in "top customers" style metrics
    top_n: int = Field(default=10, ge=1, le=100)
    # Most rows kept per dashboard metric
    max_metric_rows: int = Field(default=200, ge=1, le=10_000)

    @field_validator("aging_bucket_edges")
    @classmethod
    def edges_increase(cls, edges: list[int]) -> list[int]:
        """Bucket bounds must be positive and strictly increasing."""
        if edges[0] < 1 or any(b <= a for a, b in pairwise(edges)):
            raise ValueError("aging bucket edges must be positive and increasing")
        return edges


class CheckSettings(BaseModel):
    """Limits for the automated checks on generated views."""

    max_orphan_rate: float = Field(default=0.05, ge=0, le=1)
    max_null_rate: float = Field(default=0.05, ge=0, le=1)
    # Relative difference allowed between money totals in a view and its fact table
    reconciliation_tolerance: float = 1e-9


class Settings(BaseSettings):
    """Typed settings loaded from the environment (prefix-free) and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_nested_delimiter="__", extra="ignore"
    )

    # App
    app_env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    data_dir: Path = REPO_ROOT / "data"
    # Postgres in Docker and production; empty means a SQLite file in DATA_DIR
    database_url: str = ""
    # Redis for background jobs; empty means jobs run in a thread in the API process
    redis_url: str = ""
    # inline (run in the request, for tests), thread or arq (Redis)
    jobs_mode: Literal["inline", "thread", "arq"] = "thread"
    jobs_max_concurrent: int = 2
    jobs_timeout_seconds: int = 600
    jobs_keep_result_seconds: int = 3600
    db_pool_size: int = 5
    db_max_overflow: int = 5
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    # Build the read-only sample project at startup, for the public demo (D-037)
    demo_mode: bool = False

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

    # Join candidates
    joins: JoinSettings = Field(default_factory=JoinSettings)

    # Checks on generated views
    checks: CheckSettings = Field(default_factory=CheckSettings)

    # KPIs
    kpi: KPISettings = Field(default_factory=KPISettings)

    # Agent
    agent: AgentSettings = Field(default_factory=AgentSettings)

    # Questions in plain English
    qa: QASettings = Field(default_factory=QASettings)

    # Rate and size limits
    limits: LimitSettings = Field(default_factory=LimitSettings)

    # Language model
    llm: LLMSettings = Field(default_factory=LLMSettings)
    gemini_api_key: SecretStr = SecretStr("")

    # Tracing (optional)
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_capture_prompts: bool = False

    @property
    def llm_cache_dir(self) -> Path:
        """Folder for cached model answers (saves free-tier quota on reruns)."""
        return self.data_dir / "llm_cache"

    @property
    def db_url(self) -> str:
        """The configured database, or a local SQLite file when none is set."""
        return self.database_url or f"sqlite:///{(self.data_dir / 'joinpilot.db').resolve()}"

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
