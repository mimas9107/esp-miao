# 2026-03-07 喚醒提示音優化項目 (TODO.md)

## [Phase 1] ESP32 功能實作
- [x] 1. 引入 `esp_http_client.h`。
- [x] 2. 定義 `ACK_URL`。
- [x] 3. 實作 `send_ack_request()` 函式（快速逾時 1s）。
- [x] 4. 在 `WAKE WORD DETECTED` 與閃燈邏輯之間插入 HTTP 呼叫。

## [Phase 2] 驗證與紀錄
- [x] 1. 燒錄測試，確認伺服器正確播放提示音。
- [x] 2. 更新 `CHANGELOG.md` 至 v0.5.0。
- [x] 3. 更新 `README.md` 中的 API 說明。
- [x] 4. Git 提交變更。
