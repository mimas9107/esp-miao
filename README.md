# ESP32 Voice Agent Project 
## Project id: ESP-MIAO

本專案目標是在 **ESP32 Dev Kit v1** 上實作一個本地語音控制代理，結合 **esp-sr (Wake Word + Offline Command)** 與 **Local Server + Ollama LLM**，打造一個低延遲、可擴充、工程化的語音控制系統。

ESP32 負責語音感知與硬體控制，Server 負責語意理解與跨裝置協調。

---

## 1. Project Goals

* 在 ESP32 上實作 Always-on Wake Word（Hi 喵喵）。
* 使用 esp-sr MultiNet 處理高頻、低延遲的本地指令。
* 對於複雜語意交由 Server + Ollama LLM 解析。
* 建立 JSON Protocol 作為事件傳遞格式。
* 支援 relay、音效播放與未來 IoT 擴充。

---

## 2. System Architecture

```
User
 ↓
Mic → ESP32 (esp-sr)
        ├─ WakeNet
        ├─ MultiNet
        └─ Local Action
             ↓ fallback
          Server
            ├─ ASR
            ├─ Ollama Intent
            ├─ Device Mapper
            └─ Action Router
             ↓
          ESP32 Execute
```

設計原則：

* ESP32 只做即時、低延遲、與自身硬體相關的任務。
* Server 處理語意、跨裝置、策略與安全。

---

## 3. Responsibility Split

| Layer  | Responsibility                                           |
| ------ | -------------------------------------------------------- |
| ESP32  | Wake word, audio frontend, offline command, relay, sound |
| Server | ASR, LLM intent, device table, routing, logging          |
| LLM    | JSON intent mapping only                                 |

---

## 4. Workflow

### 4.1 Fast Path (Local)

```
Wake → esp-sr → Local Execute → Ack → Feedback
```

### 4.2 Slow Path (Server Fallback)

```
Wake → esp-sr miss → Send → ASR → Ollama → Route → Execute → Ack → Feedback
```

---

## 5. JSON Protocol Design

### 5.1 ESP32 → Server

```json
{
  "type": "command_request",
  "device_id": "esp32_01",
  "timestamp": 17574239,
  "text": "小E 開燈"
}
```

### 5.2 Server → ESP32 Action

```json
{
  "type": "action",
  "action": "relay_set",
  "target": "light",
  "value": "on",
  "sound": "success.wav"
}
```

### 5.3 ESP32 → Server Result

```json
{
  "type": "action_result",
  "status": "success"
}
```

---

## 6. esp-sr Usage Strategy

### 6.1 Wake Word

* 使用 WakeNet 預設模型。
* 採用 Hi 喵喵 作為喚醒詞。

### 6.2 Offline Command (MultiNet)

適合本地處理的指令：

* 開燈 / 關燈
* LED on / off
* 播放提示音

不適合本地處理的指令：

* 開窗簾
* 啟動掃地機
* 情境描述

MultiNet 僅作為快捷鍵分類器，而非語意理解。

---

## 7. Device Table + LLM

Server 維護裝置表：

```json
{
  "devices": [
    {"name": "light", "type": "relay", "gpio": 26}
  ]
}
```

Prompt 設計：

```
你是控制系統，只能輸出 JSON。
依照裝置表將指令轉成 action。
```

---

## 8. ESP32 State Machine

```
IDLE
 → WAKE
 → LISTEN
 → RECOGNIZE
 → LOCAL_EXECUTE | FORWARD_SERVER
 → WAIT_RESULT
 → PLAY_FEEDBACK
 → IDLE
```

---

## 9. MVP Implementation Plan

### Phase 1

* esp-sr wake
* esp-sr command
* relay control

### Phase 2

* unknown fallback
* server ASR + ollama

### Phase 3

* feedback audio
* logging

---
## Project follow ./WALKTHROUGH.md
## Project specification ./SPEC.md
## Project starter ./BOOTSTRAP.md

## Reference 
same as ./REFERENCE.md

* [https://github.com/espressif/esp-sr](https://github.com/espressif/esp-sr)
* [https://docs.espressif.com/projects/esp-sr](https://docs.espressif.com/projects/esp-sr)
* [https://github.com/78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
* [https://github.com/ollama/ollama](https://github.com/ollama/ollama)
* [https://docs.espressif.com/projects/esp-idf](https://docs.espressif.com/projects/esp-idf)
