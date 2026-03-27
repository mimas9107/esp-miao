# NOTES: ESP-MIAO Architecture Upgrade (Phases 1-3) - Post-Verification

## 1. Important Bug Fixes during Integration
- **MQTT Buffer Size**: Initial discovery failed because the new JSON payload (~400 bytes) exceeded the default buffer of `PubSubClient`. 
  - **Resolution**: Added `mqttClient.setBufferSize(1024)` in the Arduino code.
- **Server NameError**: `ACTION_KEYWORDS` was used in `connection.py` but not imported.
  - **Resolution**: Added the missing import in `connection.py`.

## 2. Verified Benefits
- **Multi-Device Coexistence**: Successfully registered two different ESP32 devices (Light and Fan).
- **Targeted Keywords**: The system correctly used "風扇" specific keywords for the fan device and "燈" keywords for the light, even when both were online.
- **Clean Logic**: Removing the hardcoded vacuum logic made the intent engine much more predictable and easier to debug.

## 3. Performance Observation
- Parsing latency remains low even with per-device lookup.
- The use of `ArduinoJson` on the light/fan devices did not cause any stability issues or memory exhaustion.

## 4. Next Steps
- Prepare for Phase 4: `myxiaomi` integration via MQTT Bridge.
- Ensure the vacuum Discovery payload matches the new structure.
