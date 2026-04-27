# LENS Test Reference

**Document Status**: v1.0
**Document Type**: Reference test lists and sample tests — starting points for PLAN phase
**Authority**: This document is **optional**. The Charter (DP-5: Test-list Before Code) requires that you write a test list, but does not require that the list match this reference. Use this when stuck or seeking a starting point.
**Pairs With**: `LENS_CHARTER.md` (mandatory) and `LENS_IMPLEMENTATION.md` (reference implementation context)
**Audience**: Agents during PLAN phase, human reviewers checking test coverage

---

## 0. About This Document

Per Charter DP-5, every module's implementation begins with a written, approved test list. This document offers **starting points** for that list — typical cases other implementers have found useful. You are expected to:

- Use these as a baseline, not a ceiling
- Add cases your specific context demands (DP-5 says you discover new cases during implementation; that is normal)
- Remove cases that do not apply to your context (with a one-line note in the PLAN doc explaining why)
- Re-derive everything if you believe a fundamentally different decomposition is better — surface that decision and get approval before proceeding

Sample tests in this document are **illustrations of style**, not requirements. They show the shape of a test, the depth of an assertion, the use of fakes from DP-8 — copy the shape, write your own specifics.

---

## 1. Module: Event Schema（L2 的一部分）

### 1.2 Sample Test Cases (style reference)

```python
# tests/unit/events/test_schema.py

import pytest
from pydantic import ValidationError
from lens.events.schema import EventEnvelope, NodeStarted, NodeCompleted


def test_event_envelope_requires_event_id():
    with pytest.raises(ValidationError) as exc_info:
        EventEnvelope(
            schema_version="1.0",
            timestamp="2024-04-24T10:00:00Z",
            build_id="build_42",
        )
    assert "event_id" in str(exc_info.value)


def test_event_envelope_rejects_invalid_schema_version():
    with pytest.raises(ValidationError):
        EventEnvelope(
            event_id="550e8400-e29b-41d4-a716-446655440000",
            schema_version="v1",  # must be "1.0" format
            timestamp="2024-04-24T10:00:00Z",
            build_id="build_42",
        )


def test_node_started_serialization_roundtrip():
    original = NodeStarted(
        event_id="550e8400-e29b-41d4-a716-446655440000",
        schema_version="1.0",
        timestamp="2024-04-24T10:00:00Z",
        build_id="build_42",
        node_id="node_1",
        level="flow",
        entity_id="drc_flow",
    )
    as_json = original.model_dump_json()
    reconstructed = NodeStarted.model_validate_json(as_json)
    assert reconstructed == original


def test_node_completed_exit_code_can_be_negative():
    """Signal termination (e.g. SIGKILL) reports negative exit code."""
    evt = NodeCompleted(
        event_id="550e8400-e29b-41d4-a716-446655440000",
        schema_version="1.0",
        timestamp="2024-04-24T10:00:00Z",
        build_id="build_42",
        node_id="node_1",
        level="flow",
        entity_id="drc_flow",
        exit_code=-9,
        duration_seconds=120.5,
    )
    assert evt.exit_code == -9
```

```python
# tests/unit/events/test_registry.py

def test_schema_registry_validates_valid_event(tmp_path):
    # setup: write a minimal schema file
    schema_file = tmp_path / "node_started.v1.json"
    schema_file.write_text(json.dumps({
        "type": "object",
        "required": ["event_id", "event_type"],
        "properties": {
            "event_type": {"const": "NodeStarted"},
            "event_id": {"type": "string"},
        }
    }))

    registry = SchemaRegistry(tmp_path)
    registry.validate({
        "event_type": "NodeStarted",
        "event_id": "abc-123",
    })  # should not raise
```

---

## 2. Module: Event Backbone（Kafka Adapter）

### 2.1 Test List (starting point)

These tests live under `tests/integration/backbone/` (not `tests/unit/backbone/`) because they test the Kafka adapter against a real testcontainer Kafka. **Unit tests for business modules** that consume the bus use `InMemoryEventBus` and live in those modules' test directories.

**Producer (KafkaEventBus adapter)**
1. `test_kafka_producer_sends_event_to_real_kafka`
2. `test_kafka_producer_does_not_raise_on_kafka_unavailable`
3. `test_kafka_producer_writes_to_local_buffer_on_send_failure`
4. `test_kafka_producer_flushes_local_buffer_when_kafka_recovers`
5. `test_kafka_producer_stop_flushes_pending_events`

**Consumer (KafkaEventBus adapter)**
6. `test_kafka_consumer_invokes_handler_for_each_message`
7. `test_kafka_consumer_continues_after_handler_raises_on_single_message`
8. `test_kafka_consumer_sends_poison_message_to_dlq`
9. `test_kafka_consumer_commits_offset_only_after_handler_success`
10. `test_kafka_consumer_graceful_shutdown_on_stop`

**InMemoryEventBus (test fake)**
11. `test_in_memory_bus_delivers_events_to_subscribers`
12. `test_in_memory_bus_isolates_topics`
13. `test_in_memory_bus_handler_failure_does_not_crash_bus`

### 2.2 Sample Test Cases (style reference)

#### 5.5.1 Adapter integration test (against real Kafka via testcontainer)

```python
# tests/integration/backbone/test_kafka_bus.py

@pytest.mark.asyncio
async def test_kafka_producer_does_not_raise_on_kafka_unavailable(tmp_path):
    bus = KafkaEventBus(bootstrap_servers=["localhost:9999"])  # no Kafka here
    producer = bus.producer(
        topic="build.events",
        local_buffer_path=tmp_path / "buffer.ndjson",
    )
    await producer.start()

    # Should NOT raise, should silently buffer
    await producer.send(make_test_event())

    await producer.stop()

    # Verify event was buffered locally
    assert (tmp_path / "buffer.ndjson").read_text().strip()


@pytest.mark.asyncio
async def test_kafka_producer_flushes_local_buffer_when_kafka_recovers(
    kafka_fixture,  # testcontainer Kafka fixture
    tmp_path,
):
    bus = KafkaEventBus(bootstrap_servers=[kafka_fixture.bootstrap_servers])
    producer = bus.producer(
        topic="build.events",
        local_buffer_path=tmp_path / "buffer.ndjson",
    )
    # Pre-populate buffer as if earlier Kafka failures happened
    event = make_test_event()
    (tmp_path / "buffer.ndjson").write_text(event.model_dump_json() + "\n")

    await producer.start()
    await producer.flush_buffer()
    await producer.stop()

    # Verify event is now in Kafka
    messages = kafka_fixture.consume("build.events")
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_kafka_consumer_continues_after_handler_raises_on_single_message(
    kafka_fixture,
):
    call_count = 0
    handled_events: list[dict] = []

    class FlakyHandler:
        async def handle(self, event):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("simulated handler failure")
            handled_events.append(event)

    # Send 3 events
    for i in range(3):
        kafka_fixture.send_raw("build.events", {"event_id": f"evt_{i}"})

    bus = KafkaEventBus(bootstrap_servers=[kafka_fixture.bootstrap_servers])
    consumer = bus.consumer(
        topic="build.events",
        group_id="test_group",
        handler=FlakyHandler(),
        dlq_topic="build.events.dlq",
    )
    asyncio.create_task(consumer.run())
    await asyncio.sleep(2)  # let consumer process
    await consumer.stop()

    # Handler invoked 3 times, 2 succeeded
    assert call_count == 3
    assert len(handled_events) == 2

    # Failed message in DLQ
    dlq_messages = kafka_fixture.consume("build.events.dlq")
    assert len(dlq_messages) == 1
    assert dlq_messages[0]["event_id"] == "evt_1"
```

#### 5.5.2 InMemoryEventBus unit test (no Kafka)

```python
# tests/unit/backbone/test_memory_bus.py

@pytest.mark.asyncio
async def test_in_memory_bus_delivers_events_to_subscribers():
    bus = InMemoryEventBus()
    received: list[dict] = []

    class Handler:
        async def handle(self, event):
            received.append(event)

    consumer = bus.consumer(
        topic="build.events", group_id="g1", handler=Handler()
    )
    consumer_task = asyncio.create_task(consumer.run())

    producer = bus.producer(topic="build.events")
    await producer.start()
    await producer.send(make_test_event(event_id="evt_1"))
    await producer.send(make_test_event(event_id="evt_2"))
    await producer.stop()

    await asyncio.sleep(0.05)  # let the in-memory bus deliver
    await consumer.stop()

    assert {e["event_id"] for e in received} == {"evt_1", "evt_2"}


@pytest.mark.asyncio
async def test_in_memory_bus_handler_failure_does_not_crash_bus():
    bus = InMemoryEventBus()
    seen: list[str] = []

    class Handler:
        async def handle(self, event):
            if event["event_id"] == "evt_2":
                raise RuntimeError("boom")
            seen.append(event["event_id"])

    consumer = bus.consumer(topic="t", group_id="g", handler=Handler())
    consumer_task = asyncio.create_task(consumer.run())

    producer = bus.producer(topic="t")
    await producer.start()
    for i in range(3):
        await producer.send(make_test_event(event_id=f"evt_{i+1}"))
    await producer.stop()

    await asyncio.sleep(0.05)
    await consumer.stop()

    assert seen == ["evt_1", "evt_3"]  # evt_2 raised, others continued
```

---

## 3. Module: Observer（L0: AP Event Bridge）

### 3.1 Test List (starting point)

**APStatusSource implementations**
1. `test_csv_source_parses_typical_dashboard_file`
2. `test_csv_source_returns_empty_when_file_missing`
3. `test_csv_source_handles_partially_written_file`
4. `test_log_tail_source_extracts_flow_started_events`
5. `test_log_tail_source_handles_log_rotation`

**APEventBridge (core diff logic)**
6. `test_bridge_emits_flow_started_when_new_flow_appears`
7. `test_bridge_emits_flow_completed_when_flow_transitions_to_done`
8. `test_bridge_emits_flow_failed_on_error_state`
9. `test_bridge_does_not_emit_event_for_unchanged_state`
10. `test_bridge_does_not_emit_duplicate_events_on_rerun`
11. `test_bridge_survives_source_fetch_failure`
12. `test_bridge_survives_producer_send_failure`

### 3.2 Sample Test Cases (style reference)

```python
# tests/unit/observer/test_ap_bridge.py

@pytest.mark.asyncio
async def test_bridge_emits_flow_started_when_new_flow_appears():
    # Arrange: two snapshots showing a new flow appearing
    snapshots = [
        {},  # empty
        {"flow_1": {"status": "RUNNING", "library": "A"}},
    ]
    source = FakeStatusSource(snapshots)
    producer = FakeProducer()

    bridge = APEventBridge(
        ap_status_source=source,
        producer=producer,
        poll_interval_sec=0.1,
    )

    # Act
    task = asyncio.create_task(bridge.run())
    await asyncio.sleep(0.3)  # let 2 polls happen
    await bridge.stop()

    # Assert
    sent_events = producer.sent
    flow_started_events = [e for e in sent_events if e.event_type == "FlowStarted"]
    assert len(flow_started_events) == 1
    assert flow_started_events[0].entity_id == "flow_1"


@pytest.mark.asyncio
async def test_bridge_does_not_emit_duplicate_events_on_rerun():
    """If bridge restarts and reads same state, don't re-emit past events."""
    snapshots = [
        {"flow_1": {"status": "RUNNING"}},
        {"flow_1": {"status": "RUNNING"}},  # no change
        {"flow_1": {"status": "COMPLETED"}},
    ]
    source = FakeStatusSource(snapshots)
    producer = FakeProducer()

    bridge = APEventBridge(source, producer, poll_interval_sec=0.1)

    task = asyncio.create_task(bridge.run())
    await asyncio.sleep(0.4)
    await bridge.stop()

    # 1 FlowStarted (first appearance), 1 FlowCompleted
    event_types = [e.event_type for e in producer.sent]
    assert event_types == ["FlowStarted", "FlowCompleted"]
```

---

## 4. Module: Projection（L3）

### 4.1 Test List (starting point)

**Base class**
1. `test_projection_skips_already_applied_event`
2. `test_projection_marks_event_as_applied_after_success`
3. `test_projection_does_not_mark_applied_on_failure`
4. `test_projection_transaction_rollback_on_apply_exception`

**DashboardStateProjection**
5. `test_flow_started_creates_kg_row`
6. `test_flow_started_increments_total_flows_for_existing_kg`
7. `test_flow_completed_increments_completed_flows`
8. `test_flow_failed_increments_failed_flows_and_sets_failed_status`
9. `test_kg_status_becomes_completed_when_all_flows_complete`
10. `test_unrelated_event_types_are_ignored`
11. `test_rebuild_from_empty_state_reproduces_same_result`

### 4.2 Sample Test Cases (style reference)

Note: these tests use an `InMemoryDashboardStateStore` fake. They run in milliseconds and require no PostgreSQL. Integration tests against real PostgreSQL live in `tests/integration/`.

```python
# tests/unit/projection/test_dashboard_state.py

import pytest
from lens.projection.dashboard_state import DashboardStateProjection
from tests.unit.projection.fakes import InMemoryDashboardStateStore


@pytest.mark.asyncio
async def test_flow_started_creates_kg_row():
    store = InMemoryDashboardStateStore()
    projection = DashboardStateProjection(store=store)

    event = {
        "event_id": "evt_1",
        "event_type": "FlowStarted",
        "timestamp": "2024-04-24T10:00:00Z",
        "build_id": "build_42",
        "entity_id": "drc_flow",
        "level": "flow",
    }
    await projection.handle(event)

    kg = store.get_kg("build_42")
    assert kg is not None
    assert kg["status"] == "RUNNING"
    assert kg["total_flows"] == 1


@pytest.mark.asyncio
async def test_projection_skips_already_applied_event():
    store = InMemoryDashboardStateStore()
    projection = DashboardStateProjection(store=store)

    event = {
        "event_id": "evt_1",
        "event_type": "FlowStarted",
        "build_id": "build_42",
        "entity_id": "drc_flow",
        # ...
    }
    await projection.handle(event)
    await projection.handle(event)  # should be noop

    kg = store.get_kg("build_42")
    assert kg["total_flows"] == 1  # not 2
```

```python
# tests/unit/projection/fakes.py

class InMemoryDashboardStateStore:
    """In-memory fake of DashboardStateStore for fast unit tests."""

    def __init__(self):
        self._kgs: dict[str, dict] = {}
        self._applied: set[tuple[str, str]] = set()  # (projection_name, event_id)

    def transaction(self):
        # In-memory: no real transaction, but match the protocol
        return _NoOpTransaction()

    @property
    def dedup(self):
        return self  # fake plays both roles

    async def has_applied(self, projection_name: str, event_id: str) -> bool:
        return (projection_name, event_id) in self._applied

    async def mark_applied(self, projection_name: str, event_id: str) -> None:
        self._applied.add((projection_name, event_id))

    async def upsert_kg(self, build_id: str, fields: dict) -> None:
        existing = self._kgs.setdefault(build_id, {})
        existing.update(fields)

    async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None:
        kg = self._kgs.setdefault(build_id, {})
        kg[field] = kg.get(field, 0) + delta

    async def truncate_all(self) -> None:
        self._kgs.clear()

    # Test-only helper
    def get_kg(self, build_id: str) -> dict | None:
        return self._kgs.get(build_id)


class _NoOpTransaction:
    async def __aenter__(self): return self
    async def __aexit__(self, *exc_info): pass
    async def commit(self): pass
    async def rollback(self): pass
```

---

## 5. Module: API Server（L5）

### 5.1 Test List (starting point)

1. `test_health_endpoint_returns_ok`
2. `test_list_kgs_returns_empty_when_no_data`
3. `test_list_kgs_returns_all_active_kgs`
4. `test_list_kgs_filters_by_status`
5. `test_list_kgs_filters_by_library`
6. `test_get_kg_returns_404_for_unknown_build_id`
7. `test_get_kg_returns_full_details`
8. `test_list_libraries_aggregates_correctly`
9. `test_library_health_returns_trend_over_time`

### 5.2 Sample Test Cases (style reference)

The API depends on the `DashboardStateStore` interface (defined in §7). Unit tests inject an `InMemoryDashboardStateStore` populated directly via its public methods — no SQL, no PostgreSQL, no migrations.

```python
# tests/unit/api/test_kgs_endpoint.py

@pytest.fixture
def store_with_test_data():
    store = InMemoryDashboardStateStore()
    # Use the store's public interface to seed data
    asyncio.run(store.upsert_kg("b1", {"status": "RUNNING", "library": "A"}))
    asyncio.run(store.upsert_kg("b2", {"status": "COMPLETED", "library": "A"}))
    asyncio.run(store.upsert_kg("b3", {"status": "RUNNING", "library": "B"}))
    return store


@pytest.fixture
def test_client(store_with_test_data):
    from lens.api.app import create_app
    app = create_app(dashboard_store=store_with_test_data)
    return TestClient(app)


def test_list_kgs_filters_by_status(test_client):
    response = test_client.get("/api/kgs?status=RUNNING")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {kg["build_id"] for kg in data} == {"b1", "b3"}
```

Note `create_app()` accepts the store as a constructor parameter — this is the composition root pattern from DP-8. Production wiring instantiates the Postgres adapter; tests inject the in-memory fake.

---

## 6. Module: Configuration（橫切）

### 6.1 Test List (starting point)

1. `test_default_settings_can_be_instantiated`
2. `test_env_var_overrides_default`
3. `test_invalid_pg_dsn_raises_validation_error`

---

---

## Document Versioning

- **v1.0** — Initial extraction from `implementation_spec_v0.6.md`. All Test List and Sample Test Cases subsections consolidated here as optional reference.

---

*— End of LENS Test Reference v1.0 —*
