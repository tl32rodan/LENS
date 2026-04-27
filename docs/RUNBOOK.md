# LENS Deployment Runbook

> Brian: this is the deploy guide for an environment that has Kafka and
> Postgres reachable but **does not run Docker**. Recipe B at the bottom
> is the laptop / CI fallback that needs zero external services.

## What you need before deploying

- Python 3.12+
- A reachable Kafka broker (any version compatible with aiokafka 0.11+)
- A reachable PostgreSQL 13+ instance with a database `lens` and a user
  with `CREATE TABLE` rights
- This repository checked out at the commit you intend to deploy

## One-time setup

```sh
# 1. Create + activate a venv
python3.12 -m venv .venv
. .venv/bin/activate

# 2. Install LENS into the venv
pip install -e .

# 3. Copy the env template and edit DSNs
cp .env.example .env
$EDITOR .env
# Set LENS_KAFKA_BOOTSTRAP_SERVERS, LENS_PG_DSN, LENS_OBSERVER_CSV_PATH at minimum.

# 4. Bootstrap the database schema (idempotent — safe to re-run)
python -m lens.projection init-db
```

## Recipe A — running against real services

Three processes, started in any order. Each reads `.env` automatically.

### Observer (L0)

```sh
# Daemon: polls every LENS_OBSERVER_POLL_INTERVAL_SEC
python -m lens.observer

# Single tick (useful for cron or scripted observation)
python -m lens.observer --once
```

### Projection consumer (L3)

```sh
python -m lens.projection dashboard-state
```

### API server (L5)

```sh
uvicorn lens.api.asgi:app --host "$LENS_API_HOST" --port "$LENS_API_PORT"

# Smoke
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/kgs | jq .
```

### Stopping

Each process terminates on `SIGINT` / `SIGTERM`. The observer and
projection consumer drain in-flight work; the API exits immediately.

### Troubleshooting

- **Postgres connection rejected**: confirm `LENS_PG_DSN` uses
  `postgresql+asyncpg://...` (the validator in `lens.config` rejects
  anything else at startup).
- **Producer logs say "buffered to ..."**: Kafka is unreachable. Events
  land in `LENS_PRODUCER_LOCAL_BUFFER_PATH` (ndjson, per IR-3) and drain
  automatically on the next successful broker connection.
- **API returns empty `/api/kgs`**: the projection hasn't consumed any
  events yet (or the observer hasn't emitted any). Check that the
  observer logs flush, the projection log shows it advanced past
  events, and the topic name matches `LENS_KAFKA_TOPIC_EVENTS` on
  both sides.
- **DDL conflicts on re-run**: every CREATE uses `IF NOT EXISTS`; if
  you see a hard failure, the schema in your DB diverges from
  `lens.projection.postgres_schema`. Inspect manually before forcing.

## Recipe B — laptop / CI mode (no external services)

Same processes, but flip the adapter switches:

```sh
export LENS_BUS=memory
export LENS_PROJECTION_STORE=memory
```

Caveat: in-memory state is per-process, so all three processes (observer,
projection consumer, API) must run inside the **same Python process**
to share the bus and store. The end-to-end test
(`tests/e2e/test_demo_in_memory.py`) shows the wiring; for a real
single-process demo you'd compose them in a small script.

For Phase 0 the in-memory mode exists primarily for tests and CI; the
real deploy uses Recipe A.

## Operational notes

- **Logging**: structured stderr lines via stdlib `logging`. Level via
  `LENS_LOG_LEVEL`. The deployment environment is responsible for
  capturing stderr.
- **Schema migrations**: Phase 0 ships no Alembic. Schema changes after
  Phase 0 will be packaged as the first Alembic baseline migration.
- **Integration tests**: `pytest -m integration` (requires real Kafka +
  PG reachable). Not in CI per the no-Docker decision; run manually
  before any change that touches `kafka_bus.py` or `postgres_adapter.py`.

## Verifying a fresh deploy

```sh
# 1. Health check
curl -s http://localhost:8000/health
# expected: {"status": "ok"}

# 2. Seed AP CSV with one running flow
cat > $LENS_OBSERVER_CSV_PATH <<'EOF'
flow_id,library,owner,state,started_at,completed_at,error_message
demo_flow,demoLib,brian,RUNNING,2026-04-27T10:00:00+00:00,,
EOF

# 3. Wait a poll tick (or run --once)
python -m lens.observer --once

# 4. Confirm the KG appears via the API
curl -s "http://localhost:8000/api/kgs" | jq .
# expected: at least one row with build_id=$LENS_OBSERVER_BUILD_ID
```

If step 4 returns the seeded KG, the deploy is healthy.
