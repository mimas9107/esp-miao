# 審查要點 (REVIEW_TODO) - 2026-03-19

## 核心邏輯審查
- [x] **去中心化驗證**：確認 `connection.py` 中不再含有任何靜態裝置 ID 或別名。
- [x] **下線機制驗證**：確認 `on_message` 處理器能正確解析 `status: offline` 並調用 `remove_device`。
- [x] **通訊一致性**：確認 `dispatch.py` 已完全移除 HTTP 相關代碼與 `httpx` 依賴。
- [x] **模型完整性**：確認 `Device` 模型已移除 `api_url`，避免後續 Discovery 誤填。

## 韌體審查 (Mock/Ref)
- [x] **LWT 配置**：確認 `esp32-smart-light.ino` 與 `esp32_smart_fan.ino` 的 `mqttClient.connect` 參數包含 LWT topic 與 payload。
- [x] **Retain 標記**：確認 Discovery 與 Status 訊息發布時皆使用了 `retain=True`。

## 版本管理審查
- [x] **版本號同步**：`CHANGELOG.md`, `version.py`, `__init__.py` 皆已更新為 `0.7.1`。
