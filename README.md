# ESP-MIAO (智慧語音控制系統)

> **Version: 0.6.6**
> 
> 本專案為一個基於 ESP32 的智慧語音控制系統，具備 **Edge Impulse 喚醒詞偵測**、**即時串流音訊傳輸** 以及 **視覺化動畫 UI (Eye UI)**。系統透過語音喚醒 "heymiaomiao" 後，將音訊即時傳送至伺服器進行 ASR 與 LLM 意圖解析，並透過 MQTT 控制 IoT 裝置。

---

## 1. 專案結構 (Project Structure)

```text
esp-miao/
├── firmware/
│   ├── esp32_edge_impulse/      # 主要韌體 (ESP-IDF v5.x)
│   │   ├── components/          #   - UI 狀態機、Eye UI、TFT 驅動
│   │   ├── main/                #   - 主邏輯、音訊管線、WebSocket
│   │   └── model-parameters/    #   - Edge Impulse 模型參數
│   ├── esp32_client/            # 備用 Arduino Client 韌體
│   └── mic_frontend_v1/         # 麥克風前端測試工具
├── src/esp_miao/                # 伺服器核心 (Python/FastAPI)
│   ├── app.py                   #   - 消息路由與處理中心
│   ├── audio.py                 #   - ASR (Whisper) 處理模組
│   ├── intent.py                #   - LLM (Ollama) 與關鍵字解析
│   ├── dispatch.py              #   - 指令派發 (MQTT/HTTP)
│   ├── metrics/                 #   - 系統效能監控模組
│   ├── playsound/               #   - 伺服器反饋音效資源
│   └── version.py               #   - 全域版本定義
├── develop_journal/             # 開發日誌 (PLAN/TODO/NOTES)
├── scripts/                     # 分析與自動化工具
├── tests/                       # 單元測試與整合測試
├── SPEC.md                      # 工程規格書 (Protocol/Pins)
├── CHANGELOG.md                 # 版本變更歷史
└── README.md                    # 本文件
```

---

## 2. 系統架構 (Architectural Roles)

*   **ESP32 (邊緣端 - 雙核協作)**:
    - **Core 0 (邏輯核心)**: 負責 VAD 喚醒 (Edge Impulse)、**即時音訊串流 (Real-time Binary Streaming)**。
    - **Core 1 (顯示核心)**: 負責 **Eye UI 眼睛動畫**，根據系統狀態 (Idle, Wake, Listening, Thinking, Action) 呈現不同視覺反饋。
    - **優化點**: 採用流式傳輸架構，解決 OOM 問題並顯著降低反應延遲。

*   **Server (伺服器端)**:
    - 採用 **FastAPI 模組化架構**。
    - **ASR 轉錄**: 使用 `faster-whisper` (base 模型)。
    - **意圖解析**: LLM (Ollama qwen2.5) + 關鍵字攔截雙層解析。
    - **指令派發**: MQTT / HTTP API 指令派發至終端設備。

---

## 3. 視覺狀態說明 (Eye UI)

整合 ST7735 1.8" TFT 螢幕，提供視覺反饋：
- **待機 (IDLE)**: 隨機眨眼。
- **喚醒 (WAKE)**: 睜大眼睛。
- **聆聽 (LISTENING)**: 眼睛微瞇。
- **思考 (THINKING)**: 動態捲動動畫（即時串流中）。
- **動作 (ACTION)**: 執行指令顯示開心表情。
- **錯誤 (ERROR)**: 網路或辨識失敗顯示難過/叉叉。

---

## 4. 快速開始 (Quick Start)

### 4.1 伺服器端 (Server)
本專案使用 `uv` 進行套件管理。

```bash
# 安裝依賴
uv sync

# 啟動伺服器
uv run esp-miao
```

### 4.2 ESP32 韌體 (Firmware)
```bash
cd firmware/esp32_edge_impulse
idf.py build flash monitor
```

---

## 5. 硬體腳位配置

- **I2S Mic (INMP441)**: BCK=32, WS=25, DIN=33
- **TFT Screen (ST7735)**: MOSI=23, SCLK=18, CS=16, DC=5, RST=17
- **Display Power (GPIO4)**: 顯示器電源控制
- **Status LED**: GPIO 2

---

## 6. 開發規範

- **SSOT**: `CHANGELOG.md` 為版本號唯一事實來源。
- **Protocol**: `SPEC.md` 定義通訊協議與硬體規格。
