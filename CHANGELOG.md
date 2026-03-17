# Changelog

All notable changes to this project will be documented in this file.

## [v0.6.6] - 2026-03-17

### Added
- **Display Power Management**: Implemented GPIO4-controlled display power for ST7735.
  - Auto-off after 15 seconds of idle state to save power.
  - Auto-on when leaving idle or entering active states.

### Changed
- **Eye UI**: Fixed indentation issues in `#if UI_LOG_FPS` block.

## [v0.6.5] - 2026-03-16

### Added
- **Device-Aware Intent Architecture**: Implemented dynamic per-device action keywords.
  - ESP32 devices can now self-describe their "on/off" keywords via structured Discovery payloads.
  - Server dynamic learning: `DynamicDeviceTable` now merges device-specific vocabulary during registration.
- **ArduinoJson Integration**: Switched to `ArduinoJson` for `mqtt_for_esp32` to support complex metadata.

### Changed
- **Intent Engine Refactor**: Rewrote `extract_intent_from_text` to prioritize per-device keywords over global defaults.
- **Standardized Behavior**: Removed hardcoded vacuum auto-on logic to ensure consistent UX across all devices.

### Fixed
- **MQTT Buffer Overflow**: Increased PubSubClient buffer to 1024 bytes to accommodate large Discovery JSON.
- **Server NameError**: Resolved missing import of `ACTION_KEYWORDS` in `connection.py`.

## [v0.6.0] - 2026-03-12

### Added
- **Eye UI Animation System**: Integrated an animated eye UI for real-time visual feedback.
  - Supported 6 visual states: `IDLE`, `WAKE`, `LISTENING`, `THINKING`, `ACTION`, and `ERROR`.
  - Dedicated UI task running on **ESP32 Core 1** for 30+ FPS animations.
- **State Bridge**: New `ui_state` component using FreeRTOS queues for task communication.
- **Arduino Integration**: Added `arduino-esp32` as an ESP-IDF component.

### Changed
- **Audio Architecture (OOM Fix)**: Refactored audio handling to **"Real-time Binary Streaming"**.
  - Replaced 96KB buffer with 2KB chunks to solve heap fragmentation issues.
  - Server-side processing starts immediately upon first chunk reception.

### Fixed
- **Header Conflicts**: Fixed `IPADDR_NONE` macro collision between Arduino and lwIP.
- **Memory Stability**: Heap remains stable at ~118KB during peak operation.

## [v0.5.3] - 2026-03-08

### Changed
- **Server Modularization**: Completed refactoring of `server.py` into a modular package structure.
  - Split into `audio.py`, `intent.py`, `dispatch.py`, `connection.py`, etc.
  - Improved maintainability and testability.

## [v0.5.2] - 2026-03-07

### Added
- **Wake Feedback Optimization**: Implemented HTTP `/ack` trigger.
  - ESP32 sends a non-blocking GET request immediately upon wake word detection.
  - Server plays a local acknowledgment sound to provide instant feedback.

## [v0.5.1] - 2026-03-05

### Added
- **Metrics System**: Implemented a system for tracking ASR latency, LLM fallback ratios, and success rates.
  - Added async JSONL logging for performance analysis.
- **Miao-Sync (Timestamp Alignment)**: Unified all timestamps to Unix Epoch ms (UTC).
  - Fixed 1970 initialization issues on ESP32.

## [v0.5.0] - 2026-03-04

### Added
- **Cross-Project Integration**: Integrated with `myxiaomi` via HTTP REST API.
  - Enabled control of Xiaomi ecosystem devices through local voice commands.
- **Process Management**: Implemented `asyncio` subprocess management to eliminate zombie `aplay` processes.

### Changed
- **Performance Tuning**: Disabled Uvicorn reload on RPi4, reducing idle CPU usage to ~10%.

## [v0.4.5] - 2026-03-03

### Added
- **FFT-based VAD**: Integrated advanced FFT Voice Activity Detection.
  - Improved noise resistance and distant field wake word stability.
  - Replaced basic RMS-only detection.

## [v0.4.4] - 2026-03-02

### Optimized
- **Priority Intent Parsing**: Skip LLM calls if keyword intent is clear.
- **In-Memory ASR**: Removed physical temp files, using `io.BytesIO` for faster processing.

## [v0.4.0] - 2026-03-01

### Added
- **MQTT Discovery Gateway**: Transitioned from static control to a dynamic discovery-based architecture.
- **Dynamic LLM Prompt**: LLM context now includes currently online devices from discovery.

## [v0.3.5] - 2026-02-27

### Added
- **Binary Audio Protocol**: Initial implementation of binary WebSocket frames for audio data.
- **Server-side Playback**: Integrated `aplay` for server-side audio feedback.

## [v0.3.0] - 2026-02-25

### Added
- **Edge Impulse Integration**: Replaced standard esp-sr with MFCC-based wake word detection.
- **Continuous Inference**: Implemented sliding window inference for low-latency detection.

## [v0.2.0] - 2026-02-20

### Added
- **Rule-based Intent Mapping**: Initial keyword matching for IoT control.
- **GPIO Control**: Basic relay control via ESP32.

## [v0.1.0] - 2026-02-15

### Added
- **Initial Prototype**: Basic I2S capture and WebSocket streaming architecture.
