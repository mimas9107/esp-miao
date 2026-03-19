# 開發筆記 (NOTES) - 2026-03-19

## 測試驗證記錄

### 1. 測試環境
- **MQTT Broker**: 192.168.1.16:1883 (認証: mimas/mimas)
- **Server**: esp-miao v0.7.1
- **Mock Device**: `tests/test_vacuum_integration.py` (模擬 vacuum_01)

### 2. 測試案例與結果

#### 案例 A: 動態註冊 (Discovery)
- **操作**: 啟動伺服器後，執行 `uv run tests/test_vacuum_integration.py`。
- **預期**: 伺服器應自動建立 vacuum_01 條目。
- **日誌**: 
  - `[INFO] Received MQTT message on topic: home/discovery`
  - `[INFO] Device registered/updated: vacuum_01 (vacuum)`
- **結論**: **成功**。別名（小貓、掃地機）成功映射。

#### 案例 B: 離線同步 (LWT)
- **操作**: 按下 `Ctrl+C` 結束測試腳本。
- **預期**: 伺服器應收到 LWT 訊息並移除裝置。
- **日誌**:
  - `[INFO] Received MQTT message on topic: home/vacuum_01/status`
  - `[INFO] Processing status payload: {'status': 'offline', 'device_id': 'vacuum_01'}`
  - `[INFO] Device removed: vacuum_01`
- **結論**: **成功**。修正了 myxiaomi 離線後狀態殘留的問題。

#### 案例 C: 指令派發 (MQTT Only)
- **操作**: 透過模擬器發送語音指令「小貓掃地」。
- **預期**: 伺服器應發布 MQTT 訊息，且無 HTTP 呼叫。
- **日誌**:
  - `[INFO] esp-miao.intent: Priority Logic: Keyword match successful for '小貓掃地'`
  - `[INFO] esp-miao.dispatch: MQTT Publish: [home/vacuum/command] -> START_CLEANING (for vacuum_01)`
- **結論**: **成功**。

### 3. 技術要點記錄
- **LWT 陷阱**: 正常 `disconnect()` 不會觸發 LWT，測試時需確保連線異常中斷或手動發布離線訊息。
- **版本對齊**: 必須使用 `paho-mqtt` VERSION2 回呼函數簽名，否則 `on_message` 可能不被觸發。
- **JSON 格式**: 所有 `/status` 結尾的主題現在皆預期為 JSON 格式（含 `device_id`）。

## 最終版本確認
- **Server**: v0.7.1
- **Firmware**: 對齊 v0.7.1 (LWT 支援)
- **Documentation**: SPEC.md 已同步更新
