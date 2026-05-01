# Road to MVP & Beyond（依現有文件整理的實踐順序）

> 目的：依 `LENS_CHARTER.md`、`LENS_IMPLEMENTATION.md`、`LENS_TEST_REFERENCE.md`、`CLAUDE.md` 的規範，提供可執行的落地順序。

## 0) 先決條件（開始寫碼前）
1. **以 Charter 為唯一產品真相**：先讀 `LENS_CHARTER.md` 的設計原則與分層邊界。
2. **以 CLAUDE.md 作為執行約束**：採 test-list-first、test-first、小步提交、lint/type/coverage gate。
3. **建立 MVP 範圍聲明**：Phase 1 不做 L1 execution engine，先交付觀測與可視化價值。

---

## 1) MVP Phase 1（最短可交付路徑）

### Step 1 — 定義事件契約（L2 Contract First）
- 建立事件 envelope 與核心事件模型（如 NodeStarted/NodeCompleted）。
- 建立 schema registry 與 runtime 驗證。
- 先補齊 unit tests（含 happy path、缺欄位、版本格式、序列化 roundtrip）。

**完成標準**
- 事件 schema 可被明確版本化與驗證。
- 新增事件不破壞既有 consumer（additive-only evolution）。

### Step 2 — 建 Observer（L0）把既有系統訊號送進事件流
- 建立 AP/OBF bridge 的 adapter 邊界（可替換）。
- 將外部訊號正規化為 L2 事件並發送。
- 失敗不可 silent fallback，需可觀測錯誤。

**完成標準**
- 能穩定從既有流程產生結構化事件。
- Observer 本身不耦合業務邏輯，只做觀測與轉換。

### Step 3 — 建 Event Backbone（L2 Infra, Kafka）
- Producer：可送出事件；Kafka 不可用時寫本地 buffer。
- Consumer：可逐筆處理；poison message 進 DLQ；不中斷整體流程。
- 建立對應 integration tests（真實 Kafka 測路徑）。

**完成標準**
- 事件可可靠進出 backbone。
- 發送/消費失敗路徑具可恢復能力。

### Step 4 — 建 Projection（L3）
- 實作至少一個 dashboard 所需 projection（例如 build/node 狀態彙總）。
- 套用 idempotency 與 transaction 邊界（失敗 rollback）。
- 可由事件重播重建資料狀態。

**完成標準**
- 可從事件流穩定生成查詢友善的資料模型。
- projection state 可重建、可驗證。

### Step 5 — 建 API + Dashboard（L5）
- API 只讀 projection，不直接觸碰 event 寫入。
- Dashboard 呈現 MVP 關鍵視圖（進度、失敗點、耗時）。
- 錯誤回應符合結構化 4xx/5xx 格式。

**完成標準**
- 使用者可直接看見「可行動」的 observability 訊息。
- 完成 L0→L2→L3→L5 端到端展示。

---

## 2) MVP 後（Beyond）

### Stage A — 韌性與營運化
1. Event replay 工具與流程固化。
2. DLQ triage + re-drive 機制。
3. 指標/告警（consumer lag、DLQ rate、buffer flush success）。
4. Schema governance（版本升級流程、相容性檢查）。

### Stage B — 智能層（L4）
1. 以 consumer 方式掛入 rule/agent 分析。
2. 分析結果也回寫為 L2 事件（不繞過 backbone）。
3. 漸進增加 anomaly detection、建議修復、風險評分。

### Stage C — Execution Layer（L1）
1. 僅在 L0/L2/L3/L5 成熟後導入。
2. 先做最小 orchestration 能力，再擴展策略與回滾。
3. 持續遵守 replaceable adapter，避免綁死單一執行環境。

---

## 3) 每階段共同的工程節奏
- 先 PLAN（test list）→ IMPLEMENT（test-first）→ VERIFY（coverage/type/lint gate）。
- 每個邏輯變更保持小提交：`test:` → `feat/fix:` → `refactor:`。
- 若僅文件變更，可略過 test；程式碼變更則必跑 tests + linter。

---

## 4) 建議里程碑（實務排序）
1. **M0（1 週）**：事件 schema + 單元測試框架落地。
2. **M1（2–3 週）**：Observer + Kafka backbone 最小可用。
3. **M2（2 週）**：Projection + API。
4. **M3（1–2 週）**：Dashboard demo + E2E pipeline。
5. **M4（持續）**：replay/DLQ/監控/營運手冊。
6. **M5（條件成熟後）**：L4 agent 化。
7. **M6（最後）**：L1 execution 導入。

---

## 5) 成功判準（Definition of Done）
- **MVP DoD**：
  - 端到端路徑（L0→L2→L3→L5）可重現。
  - 事件契約可版控、可驗證、可演進。
  - 關鍵模組具行為測試，新增程式碼 coverage 達標。
  - 失敗路徑可觀測、可重播、可恢復。
- **Beyond DoD**：
  - 營運事件（DLQ、lag、回補）有 SOP。
  - L4/L1 導入不破壞事件主幹與可重播特性。
