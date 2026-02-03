
# WALKTHROUGH / TODO LIST

## ESP32 Side

* [ ] Setup esp-idf / Arduino
* [ ] Integrate esp-sr
* [ ] Configure I2S mic
* [ ] Enable WakeNet
* [ ] Configure MultiNet commands
* [ ] Implement local relay driver
* [ ] Implement JSON client
* [ ] Implement fallback sender
* [ ] Implement feedback player

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

