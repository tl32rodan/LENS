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


def test_env_var_overrides_list_default_via_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """List fields accept JSON-array env values (pydantic-settings convention)."""
    from lens.config import Settings

    monkeypatch.setenv(
        "LENS_KAFKA_BOOTSTRAP_SERVERS",
        '["broker-a:9092", "broker-b:9092"]',
    )
    assert Settings().kafka_bootstrap_servers == ["broker-a:9092", "broker-b:9092"]


def test_env_var_overrides_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Path fields accept string env values and parse to Path."""
    from lens.config import Settings

    monkeypatch.setenv("LENS_OBSERVER_CSV_PATH", "/tmp/ap.csv")  # noqa: S108 — test fixture path
    assert Settings().observer_csv_path == Path("/tmp/ap.csv")  # noqa: S108


def test_settings_loads_from_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A .env file in cwd is read at construction (pydantic-settings default)."""
    from lens.config import Settings

    env_file = tmp_path / ".env"
    env_file.write_text("LENS_LOG_LEVEL=WARNING\nLENS_API_PORT=7777\n")

    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.log_level == "WARNING"
    assert settings.api_port == 7777


def test_pg_dsn_validator_accepts_asyncpg_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """A correctly-formed asyncpg DSN passes the validator."""
    from lens.config import Settings

    monkeypatch.setenv(
        "LENS_PG_DSN", "postgresql+asyncpg://user:pass@db.internal:5432/lens"
    )
    settings = Settings()
    assert settings.pg_dsn == "postgresql+asyncpg://user:pass@db.internal:5432/lens"


def test_pg_dsn_validator_rejects_non_asyncpg_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A psycopg / sync DSN must be rejected — async-first invariant."""
    from pydantic import ValidationError

    from lens.config import Settings

    monkeypatch.setenv("LENS_PG_DSN", "postgresql://user:pass@db:5432/lens")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "asyncpg" in str(exc_info.value)


def test_invalid_pg_dsn_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per docs/LENS_TEST_REFERENCE.md §6.1 #3 — garbage in, ValidationError out."""
    from pydantic import ValidationError

    from lens.config import Settings

    monkeypatch.setenv("LENS_PG_DSN", "not a dsn at all")
    with pytest.raises(ValidationError):
        Settings()


def test_unknown_env_var_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stray LENS_* env vars do not crash construction (extra='ignore')."""
    from lens.config import Settings

    monkeypatch.setenv("LENS_TOTALLY_MADE_UP_FIELD", "value")
    Settings()  # must not raise
