"""CLI entry: `python -m lens.observer [--once]`.

Polls the configured AP source on `LENS_OBSERVER_POLL_INTERVAL_SEC` ticks
and publishes diffed events to the configured EventBus. With `--once` the
process performs a single tick and exits — useful for tests, demos, and
cron-driven observation.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from lens.composition import build_observer_bridge
from lens.config import Settings
from lens.logging_setup import configure as configure_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m lens.observer")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run a single tick (fetch + emit + exit), then return",
    )
    return parser.parse_args()


async def _run_daemon() -> None:
    settings = Settings()
    bridge = build_observer_bridge(settings)
    logger.info("observer daemon starting (build_id=%s)", settings.observer_build_id)
    await bridge.run()


async def _run_once() -> None:
    settings = Settings()
    bridge = build_observer_bridge(settings)
    logger.info("observer single-shot (build_id=%s)", settings.observer_build_id)
    # Drive one tick: producer.start() → _tick() → producer.stop()
    await bridge._producer.start()
    try:
        await bridge._tick()
    finally:
        await bridge._producer.stop()


def main() -> int:
    configure_logging()
    args = parse_args()
    if args.once:
        asyncio.run(_run_once())
    else:
        asyncio.run(_run_daemon())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
