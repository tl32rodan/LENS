# LENS

**L**ayered **E**vent-driven **N**avigation **S**ystem — library build
observability and orchestration platform.

## Status

Phase-0 MVP. End-to-end walking-skeleton (CSV → bus → projection → API)
green in CI; production adapters (Kafka + Postgres) shipped and
integration-tested manually.

## Quickstart

- **Deploying**: see [`docs/RUNBOOK.md`](docs/RUNBOOK.md).
- **Configuring**: copy [`.env.example`](.env.example) to `.env` and edit
  the DSNs.
- **Architecture / why**: see [`docs/LENS_CHARTER.md`](docs/LENS_CHARTER.md).
- **One working approach**: see [`docs/LENS_IMPLEMENTATION.md`](docs/LENS_IMPLEMENTATION.md).
- **How AI agents work in this repo**: see [`CLAUDE.md`](CLAUDE.md).

## Development

```sh
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"

# Gates
ruff check src tests && ruff format --check src tests
mypy --strict src tests
pytest --cov=src/lens --cov-fail-under=90 -q

# Integration tests against real Kafka/Postgres (manual; no Docker in CI)
pytest -m integration
```
