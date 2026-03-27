# PLAN.md - Timestamp 統一修改計畫 (Final Success)

## 1. 核心決策
統一全專案時間戳記為 **Unix Epoch 毫秒 (UTC 基準)**。

## 2. 實作範圍
- **ESP32 edge_impulse**: 實作 `init_ntp` 與 WebSocket `time_sync` 處理邏輯。
- **ESP32 client**: 實作 `syncNTP` 與 WebSocket `time_sync` 處理邏輯。
- **Server**: 實作連線後主動發送 `time_sync` 訊息。
- **SPEC.md**: 更新協議定義。

## 3. 修改特點 (Key Features)
- **Miao-Sync**: 解決了嵌入式裝置在無外網 NTP 時的時間同步問題。
- **雙重日誌**: 實現了「裝置發送時間」與「伺服器處理時間」的並行紀錄。
- **時區對齊**: 統一顯示層為 CST (UTC+8)。

## 4. 驗收結果
- [x] 成功對齊兩端時間軸。
- [x] 成功修正 1970 年初始值問題。
- [x] 不影響現有語音辨識與動作執行流程。
