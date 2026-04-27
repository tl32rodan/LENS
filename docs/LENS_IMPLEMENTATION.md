# LENS Implementation Reference

**Document Status**: v1.1
**Document Type**: Reference implementation — one working approach
**Authority**: This document is **optional reading** for agents. It demonstrates *one way* to implement LENS that satisfies the Charter. You may propose better — surface the proposal, get approval, then proceed.
**Pairs With**: `LENS_CHARTER.md` (mandatory) and `LENS_TEST_REFERENCE.md` (optional starting point for test lists)
**Audience**: Agents (when stuck or seeking a starting point), human reviewers, future maintainers

---

## 0. About This Document

The Charter defines what LENS is and what it stands for. This document shows **one concrete way** to build it that satisfies the Charter.

### 0.1 How to use this document

- **As a starting point**: When implementing a module, read the relevant section here for module boundaries, interfaces, and rationale. You are not required to mirror the exact structure shown.
- **As a reference**: When making a design choice and unsure if it conflicts with the Charter, check whether this document already shows a way that resolves your tension.
- **As a proposal target**: If you find this document wrong or stale, fix it via a `docs:` PR — the Charter's DP-7 (Spec Drives, Code Follows) governs that update.

### 0.2 Where deviation is welcome

- File layout details (specific directory names within a module)
- Internal helper function structure
- Choice of helper libraries within an already-approved dependency tree
- Refactor patterns that preserve module contract

### 0.3 Where deviation requires approval

- Public interfaces of any module (the `Public Interfaces` subsection)
- Choice of an alternate adapter implementation in production wiring
- Anything that adds or removes a Charter-listed Design Principle

### 0.4 What is NOT in this document

- **Why we exist** → Charter §1
- **What the architecture is** → Charter §3
- **Test lists and sample tests** → `LENS_TEST_REFERENCE.md`
- **Phase planning, demo strategy, business framing** → whitepaper / roadmap docs

---

## 1. 全域規範

### 1.1 程式碼組織（Repository Layout）

```
repo-root/
├── pyproject.toml              # 單一 pyproject，所有 package 在這
├── README.md
├── CLAUDE.md                   # Agent execution contract（root，第一眼可見）
├── docs/
│   ├── LENS_CHARTER.md         # 核心精神（mandatory read）
│   ├── LENS_IMPLEMENTATION.md  # 本文件（reference implementation）
│   ├── LENS_TEST_REFERENCE.md  # test list 參考起點
│   ├── event_schemas/          # 所有 event schema（版控化）
│   │   ├── node_started.v1.json
│   │   ├── node_completed.v1.json
│   │   └── ...
│   └── adr/                    # Architecture Decision Records
│       └── 0001-*.md
├── src/
│   ├── lens/                   # LENS 主 package
│   │   ├── __init__.py
│   │   ├── events/             # L2: event definitions
│   │   │   ├── __init__.py
│   │   │   ├── schema.py       # Pydantic models
│   │   │   └── registry.py     # schema registry loader
│   │   ├── observer/           # L0: observer & adapter
│   │   │   ├── __init__.py
│   │   │   ├── ap_bridge.py
│   │   │   └── emitter.py
│   │   ├── backbone/           # L2: Kafka producer/consumer infra
│   │   │   ├── __init__.py
│   │   │   ├── producer.py
│   │   │   └── consumer.py
│   │   ├── projection/         # L3: projections
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # ProjectionConsumer ABC
│   │   │   ├── dashboard_state.py
│   │   │   └── library_metrics.py
│   │   └── api/                # L5: API server
│   │       ├── __init__.py
│   │       ├── app.py
│   │       └── routes/
│   └── lens_ui/                # L5: UI (TypeScript/React)
│       └── ...
├── tests/
│   ├── unit/                   # 對應 src/lens 的 unit tests
│   │   ├── events/
│   │   ├── observer/
│   │   ├── backbone/
│   │   ├── projection/
│   │   └── api/
│   ├── integration/            # 跨 module 的 contract tests
│   │   ├── test_observer_to_kafka.py
│   │   ├── test_kafka_to_projection.py
│   │   └── test_projection_to_api.py
│   └── e2e/                    # 端到端（啟動真實 Kafka + PG）
│       └── test_full_pipeline.py
├── scripts/
│   ├── dev_kafka.sh            # 本地 Kafka 啟動
│   └── dev_pg.sh               # 本地 PostgreSQL 啟動
└── docker-compose.yml          # 本地 dev 環境
```

### 1.2 Coding Standards (Tooling Spec)

These specify *what tools* enforce code quality. *How to comply* (TDD, commit cadence) is in CLAUDE.md §3-§4.

- **Python 版本**：3.12+
- **Type hints**：強制，所有 public function / method 必須 typed
- **mypy**：`strict` mode，CI 阻擋 mypy error
- **ruff**：作為 lint + format，rule set 參見 `pyproject.toml`
- **Docstring 規則**：所有 public class / function 必須 docstring；格式：Google style
- **Line length**：100
- **Import ordering**：由 ruff 管理
- **Coverage target**：新增程式碼 ≥ 90%（CI gate；參見 CLAUDE.md §4）

### 1.3 命名慣例

- **Package / module**：`snake_case`
- **Class**：`PascalCase`
- **Function / variable**：`snake_case`
- **Constant**：`UPPER_SNAKE_CASE`
- **Event type**：`PascalCase`（e.g., `NodeStarted`, `FlowCompleted`）
- **Kafka topic**：`dot.separated.lower`（e.g., `build.events`）
- **PostgreSQL table**：`snake_case`，prefix by projection（e.g., `dashboard_kg_state`）
- **Test function**：`test_<subject>_<expected_behavior>`
  - Good: `test_event_parser_rejects_missing_schema_version`
  - Bad: `test_parser_1`, `test_it_works`

### 1.4 Git / Commit 規範

Branch naming + commit-message structural rules:

- **Branch**：`feature/<short-desc>`、`fix/<short-desc>`、`refactor/<short-desc>`、`docs/<short-desc>`、`chore/<short-desc>`
- **Commit message**：Conventional Commits（`feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`）
- **PR 規則**：任何 PR 必須有 test、新增程式碼 coverage ≥ 90%

**Commit cadence and TDD-driven commit pattern** are governed by CLAUDE.md (§3.2 — Commit Pattern, §1 IR-1 / IR-2). Do not duplicate those rules here.

### 1.5 錯誤處理原則 (System-level)

The high-level principle is in DP-6 (§1). Module-specific error-handling contracts:

- **Schema validation**：raise `lens.events.exceptions.SchemaValidationError`（in §4 module）
- **Producer**：local buffer on send failure（NOT silent — emits structured retry events; see §5 module）
- **Consumer**：poison message → DLQ topic, processing continues（see §5 module）
- **Projection**：apply failure → transaction rollback, do not mark event as applied（see §7 module）
- **API**：errors return structured 4xx/5xx with `{ "error": { "code": ..., "message": ..., "details": ... } }`

---

## 2. Module: Event Schema（L2 的一部分）

### 2.1 Design Rationale

Event schema 是整個平台**最重要的 contract**。一旦釋出，consumer 會依賴這個 schema，未來難以 breaking change。因此：

- **Schema 必須 additive-only evolution**：新增 field OK，移除 / 改型別禁止
- **Schema 檔案本身用 Git 版控**：在 `docs/event_schemas/` 下
- **每個 event 獨立 schema 檔案**：以 `<event_name>.v<version>.json` 命名
- **Code 裡用 Pydantic model 對應 schema**，執行時用 JSON Schema 驗證

### 2.2 Responsibilities

**DOES**
- 定義所有 event 的 Pydantic model
- 從 JSON Schema 檔案載入並提供 runtime validation
- 提供 event envelope（common fields: event_id, timestamp, schema_version, ...）

**DOES NOT**
- 不負責 Kafka producer / consumer（那是 Backbone 的事）
- 不負責 event 的業務語意（那是 Observer 或 Projection 的事）

### 2.3 Public Interfaces

```python
# src/lens/events/schema.py

from typing import Literal
from datetime import datetime
from pydantic import BaseModel, Field

class EventEnvelope(BaseModel):
    """Common fields for all events."""
    event_id: str = Field(..., description="UUID v4")
    schema_version: str = Field(..., pattern=r"^\d+\.\d+$")
    timestamp: datetime
    build_id: str
    parent_event_id: str | None = None

class NodeStarted(EventEnvelope):
    event_type: Literal["NodeStarted"] = "NodeStarted"
    node_id: str
    level: Literal["build", "library", "flow", "pvt", "cell"]
    entity_id: str
    input_hash: str | None = None   # Phase 2+
    resource_request: dict[str, int] | None = None

class NodeCompleted(EventEnvelope):
    event_type: Literal["NodeCompleted"] = "NodeCompleted"
    node_id: str
    level: Literal["build", "library", "flow", "pvt", "cell"]
    entity_id: str
    exit_code: int
    duration_seconds: float
    output_hash: str | None = None

# ...其他 event 類型省略

# src/lens/events/registry.py

class SchemaRegistry:
    def __init__(self, schema_dir: Path): ...
    def validate(self, event_dict: dict) -> None:
        """Raise SchemaValidationError if invalid."""
    def get_schema(self, event_type: str, version: str) -> dict: ...
```

### 2.6 Implementation Notes

- Pydantic 的 `model_config = ConfigDict(extra="forbid")` 防止未知 field 被悄悄接受
- 考慮用 `pydantic.discriminated_unions` 讓 event 多型 parse（`Union[NodeStarted, NodeCompleted, ...]`）
- JSON Schema 檔可由 Pydantic 自動產生：`NodeStarted.model_json_schema()`——但**實作初期建議手寫 JSON Schema**，以驗證 human-facing schema 的設計品質

### 2.7 Phase 0 MVP Scope

- Event Envelope + `NodeStarted` + `NodeCompleted` + `FlowStarted` + `FlowCompleted` + `FlowFailed`
- 5 個 event type、1 個 version
- 手寫 JSON Schema 檔 + Pydantic model

### 2.8 Phase 1 Full Scope

- 追加 `ResourceGranted`, `ResourceReleased`, `NodeLogEmitted` 等 runtime 相關 event
- 加入 `event_type` 的 discriminated union
- CI 整合：JSON Schema 與 Pydantic model 一致性檢查

---

## 3. Module: Event Backbone（Kafka Adapter）

### 3.1 Design Rationale

這一層是 **Kafka 的 adapter 實作**，符合 DP-8。它定義了三個 interface（在 §5.3），而 Kafka 是其中的具體實作。其他模組（Observer、Projection consumer）只與 interface 互動，從不直接 import aiokafka。

這一層也定義了**重要的 error handling 語意**：
- Producer 端**必須非阻塞**——舊 AP 不能因為 Kafka 慢或斷而變慢
- Consumer 端**必須容錯**——poison message 不能卡死整條 pipeline

這些不是 nice-to-have，是 platform 可運行的前提。

**測試策略**（per DP-8，**adapter-first sequencing**）：

實作順序：
1. **Protocol 先**：`bus.py` 的 `EventBus` / `EventProducer` / `EventConsumer` 從 day 1 就存在；business logic 一律 target Protocol（DP-8 末態不變）。
2. **Kafka adapter 次之**：`KafkaEventBus` 連同 testcontainer 整合測試先上線，確保 wire 對 Kafka 協議正確、failure mode（unavailable / poison message）行為符合契約。這是「先打通真實連線」的具體形式。
3. **InMemory fake 緊接著補**：`InMemoryEventBus` 在 Kafka adapter 完成後立刻補上（同 module 下一個 commit cycle），目的是為 Week 3+ 的 Observer / Projection 等業務模組 unit test 解鎖無 docker 的快測。

測試分布：
- **Unit tests** for business logic that *uses* the bus → use `InMemoryEventBus` fake (no Kafka)
- **Adapter integration tests** for `KafkaEventBus` itself → use testcontainer Kafka, prove the adapter speaks the protocol correctly
- The adapter integration tests are the only place where `kafka_fixture` is acceptable

注意：在 fake 補上之前的窗口（Kafka adapter 開發期間），不允許業務模組（Observer/Projection）begin TDD —— 序列化等資料處理邏輯（如 `lens.events.schema`）可以先做，因為它們不依賴 bus。

### 3.2 Responsibilities

**DOES**
- 定義 `EventBus`, `EventProducer`, `EventConsumer` interface（per DP-8）
- 提供 `KafkaEventBus`：production adapter，wraps aiokafka
- 提供 `InMemoryEventBus`：test fake
- Production adapter 管理 connection lifecycle、retry、DLQ

**DOES NOT**
- 不關心 event 語意（那是 schema module）
- 不做 projection（那是 projection module）
- 業務模組不直接依賴此模組的具體 class，只依賴 interface

### 3.3 Public Interfaces

```python
# src/lens/backbone/bus.py — interfaces (DP-8)

from typing import Protocol, AsyncIterator
from pathlib import Path
from lens.events.schema import EventEnvelope


class EventProducer(Protocol):
    """Sends events. Fire-and-forget; never blocks on broker availability."""
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def send(self, event: EventEnvelope) -> None: ...


class EventHandler(Protocol):
    async def handle(self, event: dict) -> None: ...


class EventConsumer(Protocol):
    """Consumes events; delegates to a handler. Tolerates poison messages."""
    async def run(self) -> None: ...
    async def stop(self) -> None: ...


class EventBus(Protocol):
    """Factory for producers and consumers. Hides Kafka-specific concepts."""
    def producer(
        self, topic: str, *, local_buffer_path: Path | None = None
    ) -> EventProducer: ...
    def consumer(
        self, topic: str, *, group_id: str, handler: EventHandler,
        dlq_topic: str | None = None,
    ) -> EventConsumer: ...
```

```python
# src/lens/backbone/kafka_bus.py — production adapter
# This module imports aiokafka. Other business-logic modules MUST NOT.

import aiokafka  # OK: this IS the adapter
from .bus import EventBus, EventProducer, EventConsumer, EventHandler

class KafkaEventBus:
    def __init__(self, bootstrap_servers: list[str]): ...
    def producer(self, topic, *, local_buffer_path=None) -> EventProducer:
        return _KafkaProducer(self.bootstrap_servers, topic, local_buffer_path)
    def consumer(self, topic, *, group_id, handler, dlq_topic=None) -> EventConsumer:
        return _KafkaConsumer(self.bootstrap_servers, topic, group_id, handler, dlq_topic)
```

```python
# src/lens/backbone/memory_bus.py — test fake

class InMemoryEventBus:
    """In-memory pub-sub for fast unit tests of bus consumers."""
    def __init__(self):
        self._topics: dict[str, list[EventEnvelope]] = {}
        self._subscribers: dict[str, list[EventHandler]] = {}
    # ... producer / consumer factory returning in-memory variants
```

### 3.6 Implementation Notes

- `aiokafka` 是 async-first，比 `confluent-kafka-python` 對 asyncio 友好
- Local buffer 建議用 `ndjson`（newline-delimited JSON），append-only、crash-safe、可手工檢視
- DLQ topic 另建不同 topic 名稱（`build.events.dlq`），不要混在主 topic
- Graceful shutdown：收到 SIGTERM → 停止接新 message → flush in-flight → commit offsets → close

### 3.7 Phase 0 MVP Scope

- Producer 的基本 send + local buffer（DLQ 先用 local file）
- Consumer 的 basic loop + handler dispatch
- 尚未做 Kafka DLQ topic——先 log error 即可

### 3.8 Phase 1 Full Scope

- Producer 完整 retry + recovery
- Consumer 的 DLQ 機制完整
- Prometheus metrics（send 成功率、consumer lag）

---

## 4. Module: Observer（L0: AP Event Bridge）

### 4.1 Design Rationale

**Observer 的設計有一個核心約束：絕對不能影響舊 AP 的執行**。這排除了：
- 同步 blocking call（例如 Kafka producer 發送失敗阻擋 AP）
- 侵入式 hook（改 AP 原始碼）

實作策略：**AP 的執行 state 變化透過 polling AP 自己的輸出（log file / status file / CSV dashboard）來偵測**。這讓 Observer 完全 decoupled，但也意味著 event latency 會有 polling interval 級的延遲（幾秒到幾十秒，可接受）。

### 4.2 Responsibilities

**DOES**
- 定期 poll 舊 AP 的狀態輸出（log file、status file、CSV 等）
- 將狀態變化 diff 出來轉為 event
- 透過 `EventProducer` 送出

**DOES NOT**
- 不修改舊 AP
- 不讀 AP 的內部資料結構
- 不對 AP 做任何寫操作

### 4.3 Public Interfaces

```python
# src/lens/observer/ap_bridge.py

class APEventBridge:
    def __init__(
        self,
        ap_status_source: APStatusSource,  # abstract source
        producer: EventProducer,
        poll_interval_sec: float = 5.0,
    ): ...

    async def run(self) -> None: ...
    async def stop(self) -> None: ...


class APStatusSource(Protocol):
    async def fetch_snapshot(self) -> dict[str, Any]:
        """Return current state of all flows being tracked."""


class CSVStatusSource(APStatusSource):
    """Read AP's CSV dashboard file."""
    def __init__(self, csv_path: Path): ...


class LogTailStatusSource(APStatusSource):
    """Tail AP's log files and parse state transitions."""
    def __init__(self, log_dir: Path, pattern: str): ...
```

### 4.6 Implementation Notes

- **狀態 diff 邏輯放在單獨的 pure function**：`diff_snapshots(old, new) -> list[Event]`。這樣 diff 邏輯容易 unit test。
- **Polling 策略**：首次啟動時讀到現存狀態**應該發 event**（否則 observer 重啟後 dashboard 看不到既有 flow）。但若此 state 在更早的 event 已經被記錄，會 duplicate——這個 tradeoff 靠 **event deduplication at projection layer** 解（見 Section 6）。
- **`APStatusSource` 先寫 `CSVStatusSource`** 就夠了，Log tail 是 nice-to-have。

### 4.7 Phase 0 MVP Scope

- `CSVStatusSource` + `APEventBridge`
- Emit `FlowStarted` / `FlowCompleted` / `FlowFailed` 三個 event
- 單一 flow、本機跑通

### 4.8 Phase 1 Full Scope

- 支援多個 flow 並行
- 加入 node-level（更細於 flow 的 event）如果 AP 有暴露
- `LogTailStatusSource` 作為 CSV 不足時的補充

---

## 5. Module: Projection（L3）

### 5.1 Design Rationale

Projection 是**從 event stream 衍生的 read-optimized view**。核心特性：
- **Idempotent**：同一個 event 被處理兩次結果一致（靠 `event_id` deduplication）
- **Rebuildable**：整張 projection table 可以透過 replay event stream 重建
- **Independent**：每個 projection 各一個 consumer，互不影響

新增一個 projection = 新增一個 `ProjectionConsumer` 子類別 + 一組 PostgreSQL table。

**Adapter sequencing**（與 §3.1 一致）：`ProjectionStore` Protocol day 1 定義；**`PostgresDashboardStateStore` adapter（連同 testcontainer PG 整合測試）先實作**，驗證 SQL 行為與 transaction 語意；**`InMemoryDashboardStateStore` fake 緊接著補**，供 `DashboardStateProjection` 的 apply 邏輯做毫秒級 unit test。Phase 1 MVP roadmap（Week 4）依此排序。

### 5.2 Responsibilities

**DOES**
- 消費 event stream
- Upsert 到 PostgreSQL projection table
- 處理 event deduplication
- 支援 full rebuild（truncate + replay）

**DOES NOT**
- 不發 event
- 不呼叫外部服務

### 5.3 Public Interfaces

Per DP-8, business logic targets a `ProjectionStore` interface. Concrete adapters (PostgreSQL via SQLAlchemy, in-memory for tests) are wired at composition root.

```python
# src/lens/projection/store.py — the interface

from typing import Protocol

class DedupTracker(Protocol):
    """Tracks which events have been applied to avoid double-processing."""
    async def has_applied(self, projection_name: str, event_id: str) -> bool: ...
    async def mark_applied(self, projection_name: str, event_id: str) -> None: ...

class ProjectionTransaction(Protocol):
    """A transactional scope. Adapter-specific implementations control isolation."""
    async def __aenter__(self) -> "ProjectionTransaction": ...
    async def __aexit__(self, *exc_info) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

class ProjectionStore(Protocol):
    """The storage substrate for a projection. Each projection has its own store
    with type-safe operations specific to that projection's schema."""
    def transaction(self) -> ProjectionTransaction: ...
    @property
    def dedup(self) -> DedupTracker: ...

# src/lens/projection/dashboard_state_store.py — interface specific to this projection

class DashboardStateStore(ProjectionStore, Protocol):
    """Storage operations for dashboard_state projection."""
    async def upsert_kg(self, build_id: str, fields: dict) -> None: ...
    async def increment_counter(self, build_id: str, field: str, delta: int = 1) -> None: ...
    async def truncate_all(self) -> None:
        """Used for projection rebuild."""

# src/lens/projection/base.py — the consumer base class

from abc import ABC, abstractmethod

class ProjectionConsumer(ABC):
    """Base class for all projections."""
    name: str  # subclass sets this; used as dedup namespace

    def __init__(self, store: ProjectionStore):
        self.store = store

    @abstractmethod
    async def apply(self, event: dict, txn: ProjectionTransaction) -> None:
        """Apply this event to the projection. Called inside a transaction."""

    async def handle(self, event: dict) -> None:
        """Called by consumer. Wraps apply() in a transaction with dedup."""
        async with self.store.transaction() as txn:
            if await self.store.dedup.has_applied(self.name, event["event_id"]):
                return
            await self.apply(event, txn)
            await self.store.dedup.mark_applied(self.name, event["event_id"])
            await txn.commit()


# src/lens/projection/dashboard_state.py — the actual projection logic

class DashboardStateProjection(ProjectionConsumer):
    """Per-KG current state for the main dashboard."""
    name = "dashboard_state"

    def __init__(self, store: DashboardStateStore):
        super().__init__(store)
        self.store: DashboardStateStore = store  # narrow type

    async def apply(self, event: dict, txn: ProjectionTransaction) -> None:
        match event["event_type"]:
            case "FlowStarted": ...
            case "FlowCompleted": ...
            case "FlowFailed": ...
            case _: pass  # ignore unrelated events
```

**Production wiring** (composition root, e.g., `src/lens/projection/wiring.py`) imports SQLAlchemy and provides `PostgresDashboardStateStore`. **Tests** use `InMemoryDashboardStateStore` — fast, deterministic, zero-infrastructure.

### 5.4 PostgreSQL Schema（for DashboardStateProjection）

The PostgreSQL schema below describes what the **`PostgresDashboardStateStore` adapter** persists. The projection logic itself does not see this schema — it only sees the `DashboardStateStore` interface methods.

```sql
CREATE TABLE projection_applied_events (
    event_id VARCHAR(64) PRIMARY KEY,
    projection_name VARCHAR(64) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE dashboard_kg_state (
    build_id VARCHAR(64) PRIMARY KEY,
    library VARCHAR(128),
    owner VARCHAR(64),
    status VARCHAR(32) NOT NULL,  -- 'RUNNING' | 'COMPLETED' | 'FAILED'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_flows INT DEFAULT 0,
    completed_flows INT DEFAULT 0,
    failed_flows INT DEFAULT 0,
    last_event_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_dashboard_kg_state_library ON dashboard_kg_state(library);
CREATE INDEX idx_dashboard_kg_state_status ON dashboard_kg_state(status);
```

### 5.7 Implementation Notes

- **Dedup table (`projection_applied_events`)**：同一個 projection 的 consumer 只看自己 applied 過的 event；不同 projection 各自獨立。
- **Transaction 邊界**：apply + mark_applied 必須在同一 transaction，確保 idempotency。
- **Rebuild procedure**：
  ```python
  async def rebuild(projection_name):
      await truncate_projection_tables(projection_name)
      await delete_from_applied_events_where_projection(projection_name)
      # 然後重新 replay Kafka 從 earliest offset
  ```

### 5.8 Phase 0 MVP Scope

- `ProjectionConsumer` base class with dedup
- `DashboardStateProjection` 基本 state transition
- 不做 library_metrics 等進階 projection

### 5.9 Phase 1 Full Scope

- 追加 `LibraryMetricsProjection`（cross-KG aggregation）
- Rebuild CLI tool（`lens-rebuild-projection --name=dashboard_state`）
- Prometheus metrics（lag、apply rate、error rate）

---

## 6. Module: API Server（L5）

### 6.1 Design Rationale

API 層是 read-only，只讀 PostgreSQL projection。**沒有直接 access event stream**——所有對外呈現的 data 都先經過 projection。這讓 API 層設計極度簡單，而且永遠跟 projection schema 同步。

### 6.2 Responsibilities

**DOES**
- 提供 REST endpoint 查詢 KG state、library metrics
- 提供 SSE (Server-Sent Events) / WebSocket 推送即時更新
- OpenAPI schema auto-generation

**DOES NOT**
- 不寫 data（read-only）
- 不 process event

### 6.3 Endpoints（Phase 0 MVP）

```
GET  /health                     → {"status": "ok"}
GET  /api/kgs                    → list of active KGs
GET  /api/kgs/{build_id}         → detail of one KG
GET  /api/libraries              → list of libraries with summary metrics
GET  /api/libraries/{library}/health → health trend for one library
```

### 6.6 Phase 0 MVP Scope

- 5 個 endpoint 的 basic version
- 無 auth（本地 dev 環境）
- 無即時推送（靜態 polling from UI）

### 6.7 Phase 1 Full Scope

- SSE 或 WebSocket 即時推送
- Auth 整合（與內部 SSO）
- Rate limiting、caching
- Prometheus metrics

---

## 7. Module: UI（L5）

**這個 module 的規格保留到 Phase 0 wireframe 完成後再補充**。

UI 不是 TDD 的重點（雖然 component-level test 仍建議寫）。暫定：
- React + TypeScript
- 資料 fetch via TanStack Query
- 元件 test with Vitest + Testing Library
- E2E with Playwright（Phase 1 才做）

---

## 8. Module: Configuration（橫切）

### 8.1 Design Rationale

所有 module 的配置統一管理。禁止 hard-coded 連線字串、port、topic name。

### 8.2 實作

```python
# src/lens/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    kafka_bootstrap_servers: list[str] = ["localhost:9092"]
    kafka_topic_events: str = "build.events"
    kafka_topic_dlq: str = "build.events.dlq"

    pg_dsn: str = "postgresql+asyncpg://lens:lens@localhost:5432/lens"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    observer_poll_interval_sec: float = 5.0
    observer_csv_path: Path = Path("/data/ap/dashboard.csv")

    log_level: str = "INFO"

    model_config = {"env_prefix": "LENS_", "env_file": ".env"}

settings = Settings()
```

本機用 `.env`，production 用環境變數。

## 9. Integration Tests

### 9.1 範圍與分類

| Test | 涉及 module | 驗證什麼 |
|---|---|---|
| `test_observer_to_kafka.py` | Observer + Backbone | AP 狀態變化 → Kafka 收到 event |
| `test_kafka_to_projection.py` | Backbone + Projection | Kafka event → PostgreSQL row 更新 |
| `test_projection_to_api.py` | Projection + API | PostgreSQL data → API response |
| `test_full_pipeline.py` (e2e) | 所有 | AP 狀態變化 → API 回傳新資料 |

### 9.2 測試環境

- 使用 **Testcontainers**（`testcontainers-python`）啟動一次性的 Kafka + PostgreSQL
- Fixture 在 session scope 啟動，test scope 清空資料
- CI 使用同一組 Docker image，local 與 CI 等價

### 9.3 Sample: test_observer_to_kafka

```python
# tests/integration/test_observer_to_kafka.py

@pytest.mark.asyncio
async def test_ap_status_change_produces_kafka_event(
    kafka_container,  # Testcontainer fixture
    tmp_path,
):
    # Setup
    csv_path = tmp_path / "dashboard.csv"
    csv_path.write_text("build_id,flow,status\n")

    bus = KafkaEventBus(bootstrap_servers=[kafka_container.bootstrap_servers])
    producer = bus.producer(
        topic="build.events",
        local_buffer_path=tmp_path / "buf.ndjson",
    )
    await producer.start()

    bridge = APEventBridge(
        ap_status_source=CSVStatusSource(csv_path),
        producer=producer,
        poll_interval_sec=0.2,
    )
    bridge_task = asyncio.create_task(bridge.run())

    # Act: simulate AP writing a new flow
    csv_path.write_text(
        "build_id,flow,status\n"
        "build_42,drc_flow,RUNNING\n"
    )
    await asyncio.sleep(0.5)

    # Assert: check Kafka
    kafka_consumer = create_test_consumer(kafka_container)
    messages = consume_all(kafka_consumer, timeout=2)

    flow_started = [m for m in messages if m["event_type"] == "FlowStarted"]
    assert len(flow_started) == 1
    assert flow_started[0]["build_id"] == "build_42"
    assert flow_started[0]["entity_id"] == "drc_flow"

    await bridge.stop()
    await producer.stop()
```

### 9.4 E2E Test

`test_full_pipeline.py` 啟動全部 component：Observer → Kafka → Projection → API，模擬 AP 寫狀態 → HTTP 查 API 看到資料。每個 PR 必跑。

---

## 10. Local Dev & CI Environment

This section documents **environment-level facts**: how to bring up the dev stack and what runs in CI. The **agent-side workflow** (TDD inner loop, phase gates, commit pattern) lives in CLAUDE.md and is not duplicated here.

### 10.1 本地啟動

```bash
# 啟動 Kafka + PostgreSQL（Docker Compose）
make dev-up

# 安裝依賴
uv sync  # 或 pip install -e ".[dev]"

# 跑 test
make test          # 全部
make test-unit     # 只 unit
make test-int      # 只 integration

# lint + type check
make lint
make typecheck

# 本地啟動 Observer
lens-observer

# 本地啟動 Projection consumer
lens-projection --name=dashboard_state

# 本地啟動 API
lens-api
```

### 10.2 CI Pipeline

```
1. ruff format --check
2. ruff check
3. mypy --strict
4. pytest tests/unit --cov=src/lens --cov-fail-under=90
5. pytest tests/integration（Testcontainers）
6. pytest tests/e2e（optional，主 branch 才跑）
```

CI gates are normative — see CLAUDE.md §4 for the override-handling protocol.

### 10.3 PR Acceptance

PR review checklist and TDD enforcement → see CLAUDE.md §2.3 (VERIFY phase) and §4 (Code Quality Gates).

---

## 11. Phase 0 實作順序（建議）

這是建議給 AI agent 的實作順序，採 **adapter-first sequencing**（每個 I/O 邊界：Protocol → 真實 adapter（testcontainer 整合測試）→ in-memory fake → 用 fake 做業務模組 unit test）。每步完成才做下一步。

### Week 1
1. Repo skeleton、pyproject.toml、CI 基本設定、pre-commit hooks
2. Docker Compose（Kafka + PostgreSQL）本地可跑
3. `lens.events.schema` — `EventEnvelope` + `NodeStarted` + `NodeCompleted` + `FlowStarted` + `FlowCompleted` + `FlowFailed` 的 Pydantic model（完整 TDD；不依賴 I/O，不受 adapter sequencing 影響）

### Week 2
4. `lens.events.registry` — SchemaRegistry + JSON Schema 檔（完整 TDD）
5. `lens.config` — Settings（TDD）
6. `lens.backbone.bus` — `EventBus`/`EventProducer`/`EventConsumer` Protocols（純 type 定義，Day 1 鎖介面）
7. `lens.backbone.kafka_bus` — `KafkaEventBus` production adapter，**先寫**；以 testcontainer Kafka 做整合測試，驗證對 Kafka 協議的 wire 正確、buffer-on-failure、DLQ、graceful shutdown 等 failure mode

### Week 3
8. `lens.backbone.memory_bus` — `InMemoryEventBus` fake，**緊接 adapter 補上**；以 fake 自身做 unit test（subscriber 派送、topic 隔離、handler 失敗不 crash）。完成後解鎖 Week 3+ 業務模組的無 docker 快測。
9. `lens.observer.ap_bridge` — `CSVStatusSource` + `APEventBridge` 的 diff 邏輯（完整 TDD，用 `InMemoryEventBus`）

### Week 4
10. `lens.projection.store` — `ProjectionStore` / `DashboardStateStore` Protocol（Day 1 鎖介面）
11. `lens.projection.dashboard_state_postgres` — `PostgresDashboardStateStore` adapter，**先寫**；以 testcontainer PG 做整合測試，驗證 upsert / dedup / transaction rollback 行為
12. PostgreSQL migration（Alembic）
13. `tests/unit/projection/fakes.py` — `InMemoryDashboardStateStore` fake，**緊接 adapter 補上**
14. `lens.projection.base` + `lens.projection.dashboard_state` — `ProjectionConsumer` base class + `DashboardStateProjection`（TDD，用 fake，毫秒級）

### Week 5（視進度）
15. `lens.api.app` — FastAPI app with basic endpoints（用 `InMemoryDashboardStateStore` 做 unit test，注入 Postgres adapter 做 integration test）
16. 第一個 integration test（Observer → Kafka → Projection → API）
17. UI wireframe 轉成初版 React component

### Week 6（視進度 + MVP polish）
18. 整體 e2e test pass
19. Deployment script
20. Phase 0 demo readiness

---

## 12. 已知的未決問題

這些問題在實作期間會浮現，現在記錄以便未來處理：

1. **AP CSV 的實際 schema 未確認**：需在 Phase 0 Week 2 之前拿到真實 sample 才能確定 parser。
2. **舊 AP 的 state transition 時機**：rerun / partial completion 等邊界情況的 CSV 變化模式，需實地觀察。
3. **Event deduplication key**：目前用 `event_id`，但 Observer 重啟時同一個 state 可能產生不同 `event_id` 的相同語意 event。待 Week 3 決定是否要加入 business-level dedup key。
4. **內部 Kafka cluster 的 partition / replication 設定**：需跟 IT 確認。
5. **PostgreSQL 的 schema migration 工具**：Alembic 還是 manual SQL？偏好 Alembic。
6. **UI 技術選型**：React vs 其他——待 Phase 0 wireframe 完成後決定。

---


---

## Document Versioning

- **v1.0** — Initial separation from `implementation_spec_v0.6.md`. Stripped Test List and Sample Test Cases sections (now in `LENS_TEST_REFERENCE.md`); removed Glossary (consolidated into `LENS_CHARTER.md` §6). Renumbered sections to start from §1.
- **v1.1** — Adopted **adapter-first sequencing** for I/O-boundary modules (Backbone §3.1, Projection §5.1, Phase 0 order §11). Protocol still defined Day 1; production adapter (Kafka, Postgres) implemented first with testcontainer integration tests; in-memory fake added immediately after to unblock business-module unit tests. DP-8 末態（business logic targets interface, fakes for unit tests）unchanged — only the construction order is reframed. CLAUDE.md and §1.1 directory tree updated to reflect docs/ relocation with CLAUDE.md staying at repo root.

---

*— End of LENS Implementation Reference v1.1 —*
