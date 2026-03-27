# TODO: ESP-MIAO Architecture Upgrade (Phases 1-3) - COMPLETED & VERIFIED

## Phase 1: Smart Light Discovery Upgrade [x]
- [x] Install/Ensure `ArduinoJson` library availability for `mqtt_for_esp32/esp32-smart-light`.
- [x] Modify `mqtt_for_esp32/esp32-smart-light/esp32-smart-light.ino`:
    - [x] Add `#include <ArduinoJson.h>`.
    - [x] Rewrite `sendDiscoveryMessage()` to use `StaticJsonDocument<1024>`.
    - [x] Include `action_keywords` in the payload.
    - [x] **Fix**: `mqttClient.setBufferSize(1024)` to support large payload.
- [x] Test: Successfully registered light and fan devices.

## Phase 2: Server Dynamic 建表 [x]
- [x] Update `src/esp_miao/models.py`:
    - [x] Add `action_keywords` to `Device` model.
- [x] Update `src/esp_miao/connection.py`:
    - [x] Implement `_action_keyword_map` in `DynamicDeviceTable`.
    - [x] **Fix**: Correctly import `ACTION_KEYWORDS` from config.
    - [x] Update `update_device()` to handle new payload.
    - [x] Implement `get_action_keywords()` with fallback.
- [x] Test: Logic implemented and verified with real devices.

## Phase 3: Intent.py 改寫 [x]
- [x] Modify `src/esp_miao/intent.py`:
    - [x] Refactor `extract_intent_from_text()` to be device-aware.
    - [x] Remove hardcoded vacuum default `on` logic.
- [x] Cleanup: Marked `ACTION_KEYWORDS` as deprecated in `config.py`.

## Success Metrics
- [x] Zero regressions: Verified via cross-device testing.
- [x] Scalability: Multiple ESP32s (Light & Fan) registered dynamically.
- [x] Consistency: Simplified intent parsing logic with better accuracy.
