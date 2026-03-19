# 2026-03-19 開發日誌：MQTT 穩定性與協定合理化

## [核心變更]

### 1. 韌體通訊協定重構 (Light_01 & Fan_01)
*   **Availability 分離**：將裝置在線狀態 (`/status`) 與功能執行狀態 (`/state`) 分開。
    *   `/status` 主題：僅發布 `{"status": "online/offline"}`。
    *   `/state` 主題：發布 `{"state": "ON/OFF", "device_id": "..."}`。
*   **穩定性強化**：
    *   **MAC Client ID**：使用 `WiFi.macAddress()` 作為 Client ID，解決同型號裝置重啟時的擠線問題。
    *   **Keep-Alive 寬容度**：從 15s 增加到 60s，解決短暫網路抖動導致的 LWT 誤判。
    *   **省電模式實驗**：
        *   `fan_01` 預設 `WIFI_PS_NONE` (高效能模式)。
        *   `light_01` 預設 `WIFI_PS_MIN_MODEM` (平衡降溫模式，適合封閉插座盒)。
    *   **JSON 報錯修復**：所有回報均改為 JSON 格式，消除伺服器端的 `JSONDecodeError`。

### 2. 伺服器容錯能力提升 (Server-side)
*   **離線標記機制**：修改 `connection.py`，收到 `offline` 訊息時僅標記 `is_online = False`，不再直接刪除裝置。
*   **意圖解析優化**：放寬 `intent.py` 的預過濾邏輯，支援簡繁體混用的關鍵字識別，並在裝置離線時能給予 LLM 解析後的反饋。
*   **狀態自動恢復**：收到任何 `/state` 或 `/status: online` 訊息時自動恢復 `is_online = True`。

## [實驗觀察]
*   **發熱測試**：`light_01` 在封閉插座盒中使用 `WIFI_PS_NONE` 有明顯溫升；改用 `WIFI_PS_MIN_MODEM` 後穩定性依然良好且溫度降低。
*   **斷線測試**：手動 Reset `fan_01` 後，伺服器能在 30 秒內自動透過 `online` 訊息重新對齊狀態，不再發生語音「聽不懂」的情況。

## [待辦事項]
- [x] 修正 fan_01 頻繁 offline 問題
- [x] 修正伺服器 JSON 解析報錯
- [x] 分離 Status 與 State 協定
- [x] 實作 MAC Address Client ID
- [ ] 觀察 light_01 在 MIN_MODEM 模式下的長期連線穩定度
