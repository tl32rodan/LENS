"""Unit tests for lens.config.

Per docs/LENS_IMPLEMENTATION.md §8.2 (Settings) and
docs/LENS_TEST_REFERENCE.md §6.1.

Each test isolates env vars via monkeypatch + os.environ.delenv() to avoid
inherited LENS_* leaking from the test runner's environment.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every LENS_* env var so each test sees pristine defaults."""
    import os

    for key in list(os.environ):
        if key.startswith("LENS_"):
            monkeypatch.delenv(key, raising=False)


def test_default_settings_can_be_instantiated() -> None:
    """With no env vars set, Settings() yields the documented defaults."""
    from lens.config import Settings

    settings = Settings()
    assert settings.kafka_bootstrap_servers == ["localhost:9092"]
    assert settings.kafka_topic_events == "build.events"
    assert settings.kafka_topic_dlq == "build.events.dlq"
    assert settings.api_host == "0.0.0.0"  # noqa: S104 — spec §8.2 default
    assert settings.api_port == 8000
    assert settings.observer_poll_interval_sec == 5.0
    assert settings.observer_csv_path == Path("/data/ap/dashboard.csv")
    assert settings.log_level == "INFO"
    assert settings.pg_dsn.startswith("postgresql+asyncpg://")


def test_env_var_with_lens_prefix_overrides_string_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting LENS_LOG_LEVEL=DEBUG overrides the default."""
    from lens.config import Settings

    monkeypatch.setenv("LENS_LOG_LEVEL", "DEBUG")
    assert Settings().log_level == "DEBUG"


def test_env_var_overrides_int_default_via_coercion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pydantic coerces string env vars into int fields."""
    from lens.config import Settings

    monkeypatch.setenv("LENS_API_PORT", "9999")
    assert Settings().api_port == 9999
