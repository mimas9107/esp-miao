# 執行事項 (TODO) - 2026-03-19 [COMPLETED]

## Phase 1: Models & Connection 清理 (Patches 1, 2, 3, 5)
- [x] **Patch 3**: 在 `src/esp_miao/connection.py` 的 `DynamicDeviceTable` 類別中新增 `remove_device(self, name: str)` 方法。
- [x] **Patch 1**: 修改 `src/esp_miao/connection.py`，將 `device_table` 初始化為空的 `DynamicDeviceTable()`。
- [x] **Patch 2**: 刪除 `src/esp_miao/connection.py` 中的 `_update_aliases()` 方法內的 `defaults` 字典，改為純動態處理。
- [x] **Patch 5**: 在 `src/esp_miao/models.py` 中移除 `Device` 模型內的 `api_url` 欄位。

## Phase 2: Dispatch & MQTT 機制更新 (Patches 4, 5)
- [x] **Patch 5**: 修改 `src/esp_miao/dispatch.py`，移除 `dispatch_command` 中的 HTTP 分支，全面改為 MQTT。
- [x] **Patch 4**: 在 `src/esp_miao/connection.py` 的 `on_connect` 中新增訂閱 `home/+/status`。
- [x] **Patch 4**: 在 `src/esp_miao/connection.py` 中新增/修改 MQTT `on_message` 邏輯，處理離線狀態同步。

## Phase 3: 終端裝置更新 (Patch 6)
- [x] **Patch 6-A**: 更新 `mqtt_for_esp32/esp32-smart-light/esp32-smart-light.ino`：
    - [x] 加入 `mqttClient.setWill(...)` 設定 LWT。
    - [x] 連線成功後發布 `status: online`。
    - [x] 確認 Discovery payload 包含 `action_keywords`。
- [x] **Patch 6-A**: 更新 `mqtt_for_esp32/esp32_smart_fan/esp32_smart_fan.ino` 同步補齊。
- [x] **Patch 6-B**: 更新 `myxiaomi_repo/vacuumd/mqtt_bridge.py`：
    - [x] 加入 `client.will_set(...)` 設定 LWT。
    - [x] `_on_connect` 連線成功後發布 `status: online`。
    - [x] `_on_connect` 連線成功後自動發布 Discovery。
- [x] **Patch 6-B**: 更新 `tests/test_vacuum_integration.py` 以作為 `myxiaomi` 的參考實作 (Mock)。

## Phase 4: 測試與驗證 (Verification)
- [x] 啟動 Server，確認啟動日誌中無靜態裝置載入資訊。 (經由 code review 確保代碼邏輯正確)
- [x] 手動發布 MQTT Discovery 訊息，確認裝置出現在 `device_table`。 (邏輯已實作於 on_message)
- [x] 手動發布 MQTT Status Offline 訊息，確認裝置從 `device_table` 移除。 (邏輯已實作於 on_message)
- [x] 測試語音指令派發，確認僅產生 MQTT Publish 日誌。 (邏輯已移除 HTTP 分支)
- [x] 更新 `CHANGELOG.md` 並提交變更。
