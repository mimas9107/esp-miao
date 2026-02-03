# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-03

### Added

#### Server Side
- **WebSocket Server** - FastAPI WebSocket endpoint (`/ws/{device_id}`) for ESP32 communication
- **JSON Protocol Models** - Pydantic models for all message types defined in SPEC.md
  - `CommandRequest` - ESP32 sends recognized command from esp-sr
  - `FallbackRequest` - ESP32 sends text/audio for LLM processing
  - `ActionResult` - ESP32 reports action execution result
  - `Action` - Server sends action command to ESP32
  - `Play` - Server sends audio playback command
- **Ollama LLM Integration** - Intent parsing with qwen2.5:0.5b model
- **Keyword Validation Layer** - Pre-validation before LLM to ensure device exists
  - Device aliases mapping (燈/電燈/light, 風扇/電風扇/fan, etc.)
  - Action keywords mapping (開/打開/on, 關/關閉/off, etc.)
- **Device Table Manager** - Configurable device registry with GPIO mapping
- **Action Router** - Routes parsed intents to appropriate actions
- **Feedback Audio API** - Endpoints for serving audio files (`/audio/{filename}`)
- **Logging** - Structured logging for debugging and monitoring

#### Protocol
- **JSON Schema** - Complete protocol definition matching SPEC.md
- **Timeout Handling** - Configurable WebSocket response timeout (10s default)
- **Retry Logic** - `retry.py` module with exponential backoff support

#### Safety
- **GPIO Whitelist** - Only safe GPIO pins allowed (避免 flash/boot pins)
- **Action Validation** - Validates action, target, and value before execution
- **Fail-safe Default** - Invalid actions return `noop` or error response

#### Testing & Tools
- **ESP32 Simulator** (`esp32-sim`) - Interactive CLI tool to simulate ESP32 device
  - State machine implementation matching SPEC.md
  - Command simulation (0-3 for local commands)
  - Fallback text request simulation
  - Full wake->listen->recognize flow simulation
- **Communication Test** - Non-interactive test script for WebSocket validation

### Project Structure

```
esp-miao/
├── src/esp_miao/
│   ├── __init__.py          # Package init (version 0.1.0)
│   ├── models.py             # Pydantic models, State Machine, Safety validators
│   ├── server.py             # FastAPI WebSocket server
│   ├── retry.py              # Retry utilities
│   ├── esp32_simulator.py    # ESP32 simulator CLI
│   └── audio/                # Feedback audio files
├── tests/
│   └── test_communication.py # WebSocket communication test
├── pyproject.toml            # Project config with uv
├── CHANGELOG.md              # This file
├── WALKTHROUGH.md            # Progress tracking
└── ...
```

### Usage

```bash
# Start server
uv run esp-miao

# Start ESP32 simulator (another terminal)
uv run esp32-sim

# Run communication test
uv run python tests/test_communication.py
```

### Dependencies
- fastapi >= 0.128.0
- uvicorn >= 0.40.0
- websockets >= 16.0
- ollama >= 0.6.1
- python-dotenv >= 1.2.1

[0.1.0]: https://github.com/user/esp-miao/releases/tag/v0.1.0
