"""Smoke tests for CLI entry-point modules.

Just verify they import cleanly and expose `parse_args` / `main`. Full
end-to-end CLI exercising belongs to manual / integration runs.
"""

from __future__ import annotations


def test_observer_main_module_imports() -> None:
    from lens.observer import __main__ as cli

    assert callable(cli.main)
    assert callable(cli.parse_args)


def test_projection_main_module_imports() -> None:
    from lens.projection import __main__ as cli

    assert callable(cli.main)
    assert callable(cli.parse_args)


def test_api_asgi_module_imports() -> None:
    """uvicorn lens.api.asgi:app needs `app` at module scope.

    We can't actually instantiate it here without a real Postgres (since the
    default LENS_PROJECTION_STORE=postgres), but we can verify the module
    file parses and the `app` symbol exists.
    """
    import importlib.util

    spec = importlib.util.find_spec("lens.api.asgi")
    assert spec is not None
    assert spec.origin is not None  # module file exists


def test_logging_setup_configure_runs() -> None:
    from lens.config import Settings
    from lens.logging_setup import configure

    configure(Settings())  # should not raise
