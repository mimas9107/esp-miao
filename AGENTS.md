---
name:          "AGENTS.md"
description:   "ESP32 喚醒詞辨識與伺服器中樞通訊規範"
created_date:  "2026/05/29 13:25:00"
modified_date: "2026/06/18 10:45:00"
project_version: "1.0.0"
document_version: "1.1.0"
agent_sign: ['human/mimas', 'gemini cli/gemini-cli']
---

# ESP-Miao 智慧語音控制系統 (AGENTS.md)

本文件定義此專案的特化開發行為。Agent 必須同時遵循工作區全域規範 (../AGENTS.md)。

## 1. 核心架構
- **ESP32 (邊緣端)**: 負責 VAD 喚醒 (heymiaomiao)，錄製音訊並透過 WebSocket 傳送。
- **Server (伺服器端)**: ASR 辨識、LLM 意圖解析、MQTT 指令發送。
## 2. 環境與開發慣例
- **Firmware**: 使用 ESP-IDF 環境，idf.py build/flash/monitor。
- **Server**: 使用 uv run 管理 Python 環境。
- **日誌**: 必須維護 ./develop_journal/ 下的 PLAN.md/TODO.md。

---
*註：本文件專注於專案業務與技術細節，通用環境指令與 Token 節約準則請查閱全域規範。*

