# ESP-MIAO (智慧語音控制系統)

> **Version: 0.5.1**
> 
> 本專案為一個基於 ESP32 的智慧語音控制系統，透過語音喚醒詞 "heymiaomiao" 觸發後，將音訊傳送至伺服器進行 ASR 與 LLM 意圖解析，並透過 MQTT 控制 IoT 裝置。

---

## 1. 系統架構 (Architectural Roles)

*   **ESP32 (邊緣端)**:
    - 負責本地端 VAD 喚醒 (辨識 "heymiaomiao")。
    - 觸發後錄製 3 秒音訊，透過 WebSocket 傳送二進位流至伺服器。
    - **注意**: ESP32 不負責任何 MQTT 指令發送或邏輯判斷。

*   **Server (伺服器端)**:
    - 採用 **FastAPI 模組化架構** (v0.5.1 重構完成)。
    - **`audio.py`**: ASR 轉錄 (faster-whisper)。
    - **`intent.py`**: LLM 意圖解析 (Ollama qwen2.5) + 關鍵字攔截。
    - **`dispatch.py`**: 指令派發 (MQTT / HTTP API)。
    - **`connection.py`**: 設備管理與 WebSocket/MQTT 連線池。
    - **`config.py`**: 統一環境變數與資源調度。

---

## 2. 快速開始 (Quick Start)

### 2.1 伺服器端 (Server)
本專案使用 `uv` 進行套件管理。

```bash
# 安裝依賴
uv sync

# 啟動伺服器
uv run esp-miao
```

### 2.2 模擬器 (Simulator)
用於在沒有硬體的情況下測試伺服器邏輯。

```bash
uv run esp32-sim
```

---

## 3. Device Discovery & MQTT Protocol (NEW v0.4.1)

本系統採 **「隨插即用 (Plug & Play)」** 架構。伺服器會動態建立語音控制地圖，您僅需撰寫終端設備 (Actuators) 的註冊代碼。

### 3.1 註冊規範 (Discovery JSON Schema)
任何新加入的 MQTT 控制板，應在連線後對 Topic: `home/discovery` 發送以下 JSON：

```json
{
  "device_id": "fan_kitchen",        // [必要] 伺服器識別用 ID (不可重複)
  "device_type": "relay",           // [必要] 設備類型 (目前支援: relay, led, sensor)
  "aliases": ["風扇", "抽風機"],      // [必要] 使用者會說出的別名 (語音辨識關鍵字)
  "control_topic": "home/fan/cmd",   // [選填] 此裝置接收指令的主題 (預設為通用主題)
  "commands": {                      // [選填] 動作值到 MQTT Payload 的對應
    "on": "FAN_ON",
    "off": "FAN_OFF"
  }
}
```

---

## 4. 開發日誌與規範 (Development & Sync)

### 4.1 開發日誌 (Logs)
本專案遵循嚴格的開發記錄規範，所有重大更動需記錄於 `./develop_journal/YYYY-MM-DD/`：
- `PLAN.md`: 當日執行計畫。
- `TODO.md`: 詳細任務清單與完成進度。
- `NOTES.md`: 技術要點與決策記錄。
- `REVIEW_TODO.md`: 項目完成後的審查清單。

### 4.2 版本追蹤 (Versioning)
- **SSOT**: `CHANGELOG.md` 為版本號的唯一事實來源。
- **Sync**: 更新版本時必須同步更新 `pyproject.toml`, `version.py` 及 `SPEC.md`。

---

## 5. Project Structure

```
esp-miao/
├── firmware/
│   ├── esp32_edge_impulse/      # Edge Impulse 喚醒詞 (主要)
├── src/esp_miao/                # Server 核心 (v0.5.1 模組化)
│   ├── app.py                   #   FastAPI 路由與消息處理
│   ├── audio.py                 #   ASR 轉錄模組
│   ├── intent.py                #   意圖解析模組
│   ├── dispatch.py              #   指令派發模組
│   ├── connection.py            #   連線與設備管理
│   ├── config.py                #   環境變數與配置
│   ├── models.py                #   Pydantic 協議模型
│   ├── version.py               #   版號定義
│   └── server.py                #   Uvicorn 啟動入口
├── tests/                       # 自動化測試 (pytest)
├── SPEC.md                      # 通訊協議規格書 (SSOT for Protocol)
├── CHANGELOG.md                 # 版本變更記錄 (SSOT for Version)
└── README.md                    # 本文件
```

---

## 6. Performance Tuning (RPi4 Optimized)

本專案針對 Raspberry Pi 4 進行了深度效能優化。您可以透過 `.env` 檔案或環境變數調整以下參數：

| 環境變數 | 預設值 | 說明 |
| :--- | :--- | :--- |
| `SERVER_RELOAD` | `0` | 是否開啟 Hot Reload。生產環境務必設為 `0` 以消除高 CPU 佔用。 |
| `LOAD_MODEL_ON_START` | `1` | 是否啟動即載入模型。 |
| `LOG_LEVEL` | `INFO` | 日誌等級。 |
| `DEBUG_AUDIO_SAVE` | `0` | 是否將錄音存檔。 |

---

*更多細節請參閱 [SPEC.md](./SPEC.md) 與 [WALKTHROUGH.md](./WALKTHROUGH.md)。*
