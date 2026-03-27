# 2026-03-08 重構任務清單 (TODO.md)

## [Phase 1] 基礎與配置遷移
- [x] 1. 建立 `config.py`，遷移所有 `os.getenv` 與路徑常量。
- [x] 2. 建立 `utils.py`，遷移 `play_local_sound` 與 `get_action_sound`。

## [Phase 2] 指令與整合模組遷移
- [x] 1. 建立 `dispatch.py`，遷移 `dispatch_command` 及其 HTTP/MQTT 依賴。
- [x] 2. 建立 `intent.py`，遷移 `extract_intent_from_text` 與 `parse_intent_with_llm`。

## [Phase 3] 核心處理模組遷移
- [x] 1. 建立 `audio.py`，遷移 `transcribe_audio` 與 Whisper 模型載入邏輯。
- [x] 2. 建立 `connection.py`，遷移 `ConnectionManager` 與 MQTT Client 實例。

## [Phase 4] 應用程式重組
- [x] 1. 將 `server.py` 剩餘的路由邏輯移動至 `app.py` 或 `main.py`。
- [x] 2. 更新 `pyproject.toml` 中的 entry points。
- [x] 3. 測試全流程（WebSocket、ASR、LLM、MQTT）。

## 額外加項
- [x] 建立 `connection.py` 時，將 `device_table` 與 `action_validator` 也進行模組化管理。
- [x] 修正 `server.py` 為純 entry point 並支援環境變數 `SERVER_RELOAD`。
