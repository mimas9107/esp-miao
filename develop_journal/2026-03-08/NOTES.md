# 2026-03-08 重構技術筆記 (NOTES.md)

## 1. 模組化後的架構
重構後的 `src/esp_miao/` 目錄結構如下：
- `config.py`: 所有環境變數、路徑常量與全局配置（如執行器、關鍵字、超時）。
- `models.py`: Pydantic 模型定義（Message, Device, ActionValidator）。
- `connection.py`: 設備管理 (`DynamicDeviceTable`)、安全驗證 (`ActionValidator`)、MQTT 客戶端 (`mqtt_client`) 與 WebSocket 連線池 (`ConnectionManager`)。
- `utils.py`: 通用輔助工具（音效播放邏輯）。
- `audio.py`: ASR 核心邏輯 (Whisper 單例與音訊轉錄)。
- `intent.py`: 意圖解析 (關鍵字匹配與 LLM 整合)。
- `dispatch.py`: 指令派發器 (MQTT 與 HTTP API)。
- `app.py`: FastAPI 應用程式定義、路由、消息處理器 (`handle_*`) 與 WebSocket 端點。
- `server.py`: 主程式入口點，負責啟動 Uvicorn。

## 2. 核心變更點
- **解耦關鍵字與 LLM**: `intent.py` 現在封裝了所有的語義解析邏輯，並能優先使用關鍵字攔截，減少 LLM 延遲。
- **單例模式模型載入**: Whisper 模型在 `audio.py` 中延遲載入，避免伺服器啟動過慢。
- **異步子進程管理**: `utils.py` 中的 `play_local_sound` 使用 `asyncio.create_subprocess_exec` 替代阻塞調用，避免卡住 WebSocket 循環。
- **統一指令對映**: 統一使用 `models.py` 中的 `COMMAND_MAP` 取代 `server.py` 內置的 `LOCAL_COMMANDS`。

## 3. 測試驗證
- 使用 `esp32_simulator.py` 驗證 `fallback_request` (LLM/Keyword 流程)。
- 測試指令: `echo "t 開燈" | uv run esp32-sim`
- 結果: 伺服器正確解析 "開燈" 為 `relay_set(light=on)` 並回傳正確的 Action。

## 4. 下一步建議
- 增加 ASR 的並行測試，觀察 RPi4 在 `inference_executor(max_workers=1)` 下的排隊行為。
- 引入單元測試框架 (pytest) 針對 `intent.py` 的解析精準度進行迴歸測試。
