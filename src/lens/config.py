"""LENS runtime configuration.

Per docs/LENS_IMPLEMENTATION.md §8.2. All fields have defaults; environment
variables (with LENS_ prefix) override at process start. A `.env` file is read
for local development.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    kafka_bootstrap_servers: list[str] = ["localhost:9092"]
    kafka_topic_events: str = "build.events"
    kafka_topic_dlq: str = "build.events.dlq"

    pg_dsn: str = "postgresql+asyncpg://lens:lens@localhost:5432/lens"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    observer_poll_interval_sec: float = 5.0
    observer_csv_path: Path = Path("/data/ap/dashboard.csv")

    log_level: str = "INFO"

    # Adapter switches (DP-8). Defaults are production: real Kafka + Postgres.
    bus: Literal["memory", "kafka"] = "kafka"
    projection_store: Literal["memory", "postgres"] = "postgres"

    # Observer / producer runtime knobs
    observer_build_id: str = "default-build"
    producer_local_buffer_path: Path = Path("/var/lib/lens/producer-buffer.ndjson")

    @field_validator("pg_dsn")
    @classmethod
    def _pg_dsn_must_be_asyncpg(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"pg_dsn must use the asyncpg driver (scheme 'postgresql+asyncpg://...'); got {v!r}"
            )
        return v
