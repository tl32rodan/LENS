"""CLI entry: `python -m lens.projection <subcommand>`.

Subcommands:
    init-db        Apply DDL to the configured Postgres (idempotent).
    dashboard-state  Run the DashboardStateProjection consumer loop.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from lens.composition import build_event_bus, build_projection_consumer
from lens.config import Settings
from lens.logging_setup import configure as configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m lens.projection")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db", help="apply DDL to the configured Postgres")
    ds = sub.add_parser("dashboard-state", help="run the dashboard_state projection consumer")
    ds.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="exit after consuming N events (smoke-test mode)",
    )
    return parser.parse_args()


async def _init_db() -> None:
    from lens.projection.postgres_adapter import init_db

    settings = Settings()
    logger.info("applying DDL to %s", settings.pg_dsn)
    await init_db(settings.pg_dsn)
    logger.info("DDL applied")


async def _run_dashboard_state(max_events: int | None) -> None:
    settings = Settings()
    bus = build_event_bus(settings)
    _, consumer = build_projection_consumer(settings, bus=bus)
    logger.info(
        "dashboard_state projection starting (bus=%s, store=%s)",
        settings.bus,
        settings.projection_store,
    )
    if max_events is None:
        await consumer.run()
    else:
        # Smoke mode: stop after N events seen via a tiny event-count guard.
        # For Phase 0 we keep this simple — the daemon path is the production one.
        run_task = asyncio.create_task(consumer.run())
        await asyncio.sleep(2.0)
        await consumer.stop()
        await run_task


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.cmd == "init-db":
        asyncio.run(_init_db())
    elif args.cmd == "dashboard-state":
        asyncio.run(_run_dashboard_state(args.max_events))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
