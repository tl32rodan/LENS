"""ASGI entry-point for `uvicorn lens.api.asgi:app`.

The unit tests still use `lens.api.app.create_app(store=...)` for DI; this
module provides the production-wired application that uvicorn discovers.
"""

from __future__ import annotations

from lens.composition import build_app
from lens.config import Settings
from lens.logging_setup import configure as configure_logging

configure_logging()
app = build_app(Settings())
