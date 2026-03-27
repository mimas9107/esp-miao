# Home Assistant (HA) Technical Notes - 2026-03-25

## 1. HA REST API 參考
- **Base URL**: `http://<ha-ip>:8123/api`
- **Authentication**: `Authorization: Bearer <token>`
- **Endpoints**:
    - `GET /api/states`: 獲取所有實體狀態。
    - `POST /api/services/<domain>/<service>`: 調用服務。
        - 範例 Body: `{"entity_id": "light.living_room_light"}`
    - `GET /api/services`: 獲取可用服務列表。

## 2. MQTT Discovery 參考
- **Topic 範例 (Light)**: `homeassistant/light/miao_light_01/config`
- **Payload 範例**:
```json
{
  "name": "Miao Light",
  "unique_id": "miao_esp32_01",
  "state_topic": "home/miao/light/state",
  "command_topic": "home/miao/light/command",
  "payload_on": "ON",
  "payload_off": "OFF",
  "device": {
    "identifiers": ["miao_esp32_01"],
    "name": "ESP-MIAO Controller",
    "model": "ESP32-S3-MIAO",
    "manufacturer": "MiaoHome"
  }
}
```

## 3. 調研結論
- **為什麼不用 Wyoming?**: Wyoming 主要針對音訊串流與 wakeword 偵測。由於 `esp-miao` 目前已經有成熟的 wake word 邏輯，且 STT/LLM 在 Server 端執行，直接透過 REST API 轉發意圖 (Intent Forwarding) 是最簡單且靈活的作法。
- **Entity 過濾**: 在同步實體時，應排除不必要的實體 (如 `sensor.uptime` 或 `sun.sun`)，僅保留可控制的 `light`, `switch`, `vacuum`, `script`, `input_boolean`。
