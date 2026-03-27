# Home Assistant (HA) Integration TODO - 2026-03-25

## 1. 協議遷移 (Discovery Migration)
- [ ] 1.1 修改 `src/esp_miao/config.py`：將 `MQTT_DISCOVERY_TOPIC` 改為 `homeassistant/+/+/config`。
- [ ] 1.2 修改 `src/esp_miao/connection.py`：實作對 HA 標準 JSON 格式的解析 (需支援 `name`, `unique_id`, `command_topic`, `state_topic`)。
- [ ] 1.3 更新 ESP32 韌體 (或模擬器)：改發送 HA 格式的 Discovery Payload。

## 2. 基礎設定 (Configuration)

## 2. 實作 HA 用戶端 (HA Client)
- [ ] 2.1 建立 `src/esp_miao/ha_client.py`：
    - [ ] 實作 `get_entities()`：抓取 HA `states` 並過濾出 `light`, `switch`, `vacuum`, `script` 等類別。
    - [ ] 實作 `call_service(domain, service, entity_id)`：發送 POST 請求至 HA。
- [ ] 2.2 在 `src/esp_miao/server.py` 的啟動腳本中，調用 `ha_client.sync_entities_to_table()`。

## 3. 整合裝置清單 (Device Registry)
- [ ] 3.1 修改 `src/esp_miao/connection.py` 中的 `DynamicDeviceTable`：
    - [ ] 支援從 HA 實體建立 `Device` 物件。
    - [ ] 設定 HA 實體的類型為 `ha_<domain>` (例如 `ha_light`)。

## 4. 指令分發 (Dispatching)
- [ ] 4.1 修改 `src/esp_miao/dispatch.py` 中的 `dispatch_command()`：
    - [ ] 檢查裝置類型，若為 `ha_*`，改走 `ha_client.call_service()`。

## 5. MQTT Discovery (自動註冊)
- [ ] 5.1 實作一個廣播函式，將 `esp-miao` 本身的開關資訊發送至 `homeassistant/switch/miao_light/config`。

## 6. 測試與驗證 (Testing)
- [ ] 6.1 使用 `esp32_simulator.py` 測試「客廳燈」等語音指令是否成功傳達至 HA。
- [ ] 6.2 檢查 HA 面板是否出現 `esp-miao` 的裝置。
