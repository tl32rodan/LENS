"""Unit tests for lens.backbone.bus — Protocol definitions.

Per docs/LENS_IMPLEMENTATION.md §3.3 (Public Interfaces).

Protocols are checked at runtime via @runtime_checkable so any concrete
adapter (KafkaEventBus, InMemoryEventBus, …) can be verified shape-wise
without inheritance.
"""

from __future__ import annotations


def test_module_exports_all_four_protocols() -> None:
    """Spec §3.3 names exactly four Protocols; the module must export each."""
    from lens.backbone import bus

    for name in ("EventProducer", "EventHandler", "EventConsumer", "EventBus"):
        assert hasattr(bus, name), f"missing Protocol: {name}"
