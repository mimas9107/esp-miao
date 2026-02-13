
# WALKTHROUGH / TODO LIST

## ESP32 Side

* [x] Setup esp-idf / Arduino (firmware/esp32_client)
* [ ] Integrate esp-sr
* [ ] Configure I2S mic
* [ ] Enable WakeNet
* [ ] Configure MultiNet commands
* [x] Implement local relay driver
* [x] Implement JSON client
* [x] Implement fallback sender
* [ ] Implement feedback player (placeholder only)

## Server Side

* [x] WebSocket server
* [x] Audio/text receiver
* [x] ASR pipeline (placeholder - integrate Whisper)
* [x] Ollama intent parser
* [x] Device table manager
* [x] Action router
* [x] Feedback audio API
* [x] Logging

## Protocol

* [x] Define schema (models.py)
* [x] Timeout handling
* [x] Retry logic (retry.py)

## Safety

* [x] GPIO whitelist
* [x] Action validation
* [x] Fail-safe default off

