# PLAN: ESP-MIAO Architecture Upgrade (Phases 1-3)

## 1. Goal
實現「裝置自描述」架構，讓 ESP-MIAO Server 能動態從裝置 Discovery 訊息中學習專屬的動作關鍵字 (Action Keywords)，從而提升意圖解析的準確性並達成關注點分離。

## 2. Phase 1: Smart Light Discovery Upgrade
### 策略
- 在 `mqtt_for_esp32/esp32-smart-light` 專案中引入 `ArduinoJson` 函式庫。
- 改寫 `sendDiscoveryMessage()`，由 String 拼接改為 JSON 對象建構。
- 加入 `action_keywords` 欄位，定義該裝置對應 "on" 與 "off" 的專屬關鍵字。

### 影響
- 提高 Discovery 訊息的結構化程度與可擴充性。

## 3. Phase 2: Server Dynamic Keyword Mapping
### 策略
- 修改 `src/esp_miao/models.py` 中的 `Device` 模型，加入 `action_keywords` 欄位。
- 在 `src/esp_miao/connection.py` 的 `DynamicDeviceTable` 中新增 `_action_keyword_map`。
- 在 `update_device()` 邏輯中，解析 Discovery Payload 並更新該映射表。
- 實現向下相容：若裝置未提供專屬關鍵字，則回退使用 `config.py` 中的全域 `ACTION_KEYWORDS`。

### 影響
- Server 端不再需要維護包含所有裝置詞彙的全域列表。

## 4. Phase 3: Intent Parsing Refactor
### 策略
- 修改 `src/esp_miao/intent.py` 中的 `extract_intent_from_text()`。
- **邏輯變更**：
    1. 首先找出 `target` 裝置。
    2. 若找到 `target`，優先從 `device_table.get_action_keywords(target)` 獲取專屬詞庫。
    3. 若無專屬詞庫，則使用全域 `ACTION_KEYWORDS`。
    4. 執行關鍵字匹配以判定 `value` ("on"/"off")。
- **清理**：移除掃地機 `if device.type == "vacuum"` 的預設啟動 hardcode 邏輯，統一系統行為。

### 影響
- 達成「裝置感知」的解析能力，避免不同類型裝置（如燈與掃地機）之間的詞彙衝突。

## 5. Risk & Mitigation
- **Arduino 記憶體限制**：ArduinoJson 的靜態緩衝區大小需精確設定 (建議 1024 bytes)。
- **一致性風險**：確保 `myxiaomi` 接入前，全域 `ACTION_KEYWORDS` 仍保留基礎詞彙以防舊裝置失效。
