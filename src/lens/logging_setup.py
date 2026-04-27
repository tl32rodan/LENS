"""Single, opinionated logging setup for CLI entry points.

Reads `LENS_LOG_LEVEL` via Settings and configures the root logger with a
plain stderr handler. Keep it boring — no JSON, no rotation; deployment
environment captures stderr.
"""

from __future__ import annotations

import logging
import sys

from lens.config import Settings


def configure(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
