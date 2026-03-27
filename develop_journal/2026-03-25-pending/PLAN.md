# Home Assistant (HA) Integration Plan - 2026-03-25

## 1. 核心目標
讓 `esp-miao` 成為一個能夠完全控制 Home Assistant 生態的「語音大腦」。
- **自動化實體同步**：Server 啟動時自動從 HA 獲取所有 Light, Switch, Script 等。
- **動態意圖解析**：將 HA 實體別名動態注入 LLM Prompt。
- **指令轉發執行**：優先將語音指令轉發至 HA Service Call，而非僅限於本地 MQTT。
- **裝置自動註冊**：讓 `esp-miao` 本身的開關/感測器透過 MQTT Discovery 自動在 HA 顯示。

## 2. 核心架構 (Strategy)

### A. 裝置註冊流程 (Unified Discovery)
1. **標準遷移**：`esp-miao` 裝置改為發送符合 HA 標準的 MQTT Discovery 訊息 (Topic: `homeassistant/<type>/<id>/config`)。
2. **多源發現**：Server 監聽 HA Discovery Topic，自動將「原生裝置」與「符合標準的第三方裝置」納入 `device_table`。
3. **命名空間**：
    - 原生裝置 ID：`esp-miao.<device_id>`
    - HA 外部實體 ID：維持原 HA `entity_id` (如 `light.kitchen`)。

### B. 控制與狀態流程
1. **指令分發 (Dispatch)**：
    - **本地路徑**：若目標為 `esp-miao.*`，Server 直接 Publish MQTT，追求零延遲。
    - **遠端路徑**：若目標為非 MQTT 的 HA 實體，透過 HA REST API 調用 Service。
2. **狀態回饋**：HA 直接從 MQTT `state_topic` 獲取狀態，Server 不介入狀態同步邏輯，維持 Stateless 輕量化。

## 3. 實施路徑 (Roadmap)

### 第一階段：連接與同步 (Connection & Sync)
- 實作 `ha_client.py` 以獲取 `/api/states`。
- 修改 `connection.py` 支援將 HA 實體匯入 `device_table`。

### 第二階段：執行轉發 (Dispatching)
- 修改 `dispatch.py`，若 `target` 是 HA 實體，則調用 `ha_client.call_service()`。

### 第三階段：反向註冊 (Discovery)
- 實作 MQTT Discovery 邏輯，讓 `esp-miao` 的裝置自動在 HA 面板出現。
