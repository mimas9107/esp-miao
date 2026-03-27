# esp-miao 架構升級計畫

> 文件版本：v2.0（依據 repo 實際狀況更新）  
> 更新日期：2026-03-16  
> 參考 repo：
> - https://github.com/mimas9107/esp-miao (v0.6.0)
> - https://github.com/mimas9107/myxiaomi / vacuumd (v0.3.9)

---

## 系統架構現況

```
[ESP32 耳朵 - ESP-IDF v5.x]
  Core 0: VAD (Edge Impulse) + 音訊串流
  Core 1: Eye UI (ST7735 TFT)
  喚醒詞 "heymiaomiao" → WebSocket 串流音訊
        ↓ WebSocket (binary streaming)
[RPi4：esp-miao server v0.6.0 - FastAPI]
  audio.py     → faster-whisper ASR
  intent.py    → 關鍵字快路徑 + Ollama qwen2.5:0.5b 慢路徑
  dispatch.py  → MQTT (落地燈) / HTTP (myxiaomi) ← 待修正
        ↓
  ┌──────────────────────┐   ┌────────────────────────────────┐
  │ ESP32 落地燈          │   │ myxiaomi / vacuumd v0.3.9      │
  │ mqtt_for_esp32/      │   │ FastAPI + Scheduler + MiCloud  │
  │ MQTT: home/light/cmd │   │ Faker + Web Dashboard          │
  └──────────────────────┘   └────────────────────────────────┘
```

### 目前問題點
- `dispatch.py` 直接呼叫 myxiaomi HTTP API → esp-miao 知道裝置實作細節（違反關注點分離）
- `ACTION_KEYWORDS` 為靜態全域常數，所有裝置共用（vacuum 專屬詞混在全域）
- ESP32 落地燈 Discovery payload 用 String 拼接，無法擴充 `action_keywords` 巢狀結構

### 核心設計原則
- **確定性優先**：關鍵字快路徑覆蓋高頻指令，LLM 只處理邊界案例
- **裝置自描述**：裝置上線時主動發 Discovery，server 動態建表
- **介面統一**：esp-miao 只認識 MQTT，不直接知道裝置底層協議
- **關注點分離**：esp-miao 負責 intent 解析與 MQTT 派發，裝置自己負責執行

---

## Phase 1：落地燈 Discovery 升級

**目標：讓裝置自帶完整的 intent metadata，包含 per-device action keywords**

**影響範圍：** `mqtt_for_esp32/` 目錄下的 Arduino 程式碼

### 背景
目前 `sendDiscoveryMessage()` 使用 String 拼接產生 JSON，只有 `aliases` 與 `commands`。
要加入巢狀的 `action_keywords`，String 拼接難以維護，需升級為 ArduinoJson。
ESP32 落地燈（非耳朵）RAM 有餘裕，可安全引入 ArduinoJson。

### 項目清單

- [ ] **引入 ArduinoJson 函式庫**
  - 在 PlatformIO `platformio.ini` 加入 `ArduinoJson` 依賴
  - 確認 RAM 用量在安全範圍

- [ ] **改寫 `sendDiscoveryMessage()`**

  目標 Discovery Payload：
  ```json
  {
    "device_id": "light_01",
    "device_type": "relay",
    "aliases": ["燈", "電燈", "燈光", "lights", "light"],
    "control_topic": "home/light_01/cmd",
    "commands": {
      "on": "ON",
      "off": "OFF"
    },
    "action_keywords": {
      "on":  ["開", "打開", "開啟", "啟動", "turn on", "on", "open", "kaitan"],
      "off": ["關", "關閉", "關掉", "停止", "turn off", "off", "close", "kuan teng"]
    }
  }
  ```

- [ ] **測試 MQTT 發布**
  - 用 MQTT Explorer 驗證新格式 JSON 正確發布到 `home/discovery`

---

## Phase 2：esp-miao Server 動態建表

**目標：server 端不再依賴靜態 `ACTION_KEYWORDS`，改由裝置 Discovery 動態合併**

**影響範圍：** `src/esp_miao/connection.py`（DeviceRegistry）、`src/esp_miao/config.py`

### 項目清單

- [ ] **`DeviceRegistry` 新增 `action_keyword_map` 結構**
  ```python
  # connection.py 新增
  device_table.action_keyword_map = {
      "light_01": {
          "on":  ["開", "打開", ...],
          "off": ["關", "關閉", ...]
      },
      "vacuum_01": {
          "on":  ["掃地", "清掃", "掃一下", ...],
          "off": ["回充", "回家", "充電", ...]
      }
  }
  ```

- [ ] **Discovery handler 解析新 payload**
  - 解析 `action_keywords` 欄位
  - 裝置上線時合併進 `action_keyword_map`
  - 裝置離線時清除對應 entry

- [ ] **向下相容 fallback 機制**
  - 若 Discovery payload 缺少 `action_keywords`
  - Fallback 到 `config.py` 現有的全域 `ACTION_KEYWORDS`

---

## Phase 3：intent.py 改寫

**目標：`extract_intent_from_text` 改用 per-device keywords**

**影響範圍：** `src/esp_miao/intent.py`

### 項目清單

- [ ] **`extract_intent_from_text` 邏輯調整**
  - 找到 `target` 之後，查 `device_table.action_keyword_map[target]`
  - 有 per-device keywords → 使用裝置專屬
  - 無 → fallback 全域 `ACTION_KEYWORDS`

- [ ] **驗證指令覆蓋率**
  - 整理現有常用指令清單（落地燈 + 掃地機）
  - 逐一測試確認 intent 解析結果沒有退步

- [ ] **全域 `ACTION_KEYWORDS` 降級**
  - 待所有裝置都有 per-device keywords 後
  - 全域常數降為純 fallback，`config.py` 中加上 deprecation 註解

---

## Phase 4：myxiaomi 接入 Discovery（正確架構）

**目標：myxiaomi 自己包 MQTT 層，esp-miao 的 `dispatch.py` 不再直接打 HTTP**

### 重要背景：myxiaomi 的實際複雜度

myxiaomi (vacuumd v0.3.9) 遠比一般裝置複雜：
- 內建 **Scheduler**（cron 排程、衝突檢測、電量守護 < 20% 拒絕啟動）
- 內建 **MiCloud Faker**（偽造小米雲端防止斷網休眠）
- 維護 **active_runs** 狀態（用於 fallback guard 衝突判定）
- 支援 **全屋 / 分區 / 指定 zone** 多種清掃模式
- **fallback guard（每小時 31 分）** 防止外部排程誤觸

因此 MQTT subscriber 設計需特別注意**不干擾現有 scheduler 邏輯**。

---

### 4-1 myxiaomi 加 MQTT Subscriber

**影響範圍：** `vacuumd/` 內新增 `mqtt_bridge.py`（或類似命名）

- [ ] **加入 paho-mqtt 依賴**（`pyproject.toml`）

- [ ] **實作 MQTT subscriber**
  - 訂閱 `home/vacuum_01/cmd`
  - 收到 `START` → 呼叫內部 `controller` 的 `start()` / `full_clean()`
  - 收到 `DOCK`  → 呼叫內部 `controller` 的 `home()`

- [ ] **與 active_runs 整合**
  - 語音指令觸發的任務也要寫入 `active_runs`
  - 確保 fallback guard（每小時 31 分）能正確辨識語音觸發，直接略過守門

- [ ] **與 Scheduler 共存**
  - 語音指令與 cron 排程同時觸發時，遵循現有衝突檢測邏輯
  - 電量守護（< 20% 拒絕）同樣適用語音指令，需正確處理錯誤回傳

- [ ] **服務啟動時同時啟動 MQTT subscriber**
  - 整合進 `start-server.sh` 或 FastAPI lifespan

---

### 4-2 myxiaomi 加 Discovery 發布

**影響範圍：** `vacuumd/` 修改啟動邏輯

- [ ] **服務啟動時發布 Discovery 到 `home/discovery`**

  目標 Discovery Payload（初版，先覆蓋基本 START / DOCK 指令）：
  ```json
  {
    "device_id": "vacuum_01",
    "device_type": "vacuum",
    "aliases": ["小貓", "掃地機", "吸塵器"],
    "control_topic": "home/vacuum_01/cmd",
    "commands": {
      "on": "START",
      "off": "DOCK"
    },
    "action_keywords": {
      "on":  ["掃地", "清掃", "掃一下", "開始掃", "啟動"],
      "off": ["回充", "回家", "停止", "充電", "回去"]
    }
  }
  ```

  > **備注**：分區清掃（zone_id）屬於進階指令，非 on/off 二元模型，
  > 留待 Phase 5 規劃，不在本次範圍內。

---

### 4-3 esp-miao 清理

**影響範圍：** `src/esp_miao/dispatch.py`

- [ ] **移除 `dispatch.py` 中直接打 myxiaomi HTTP API 的程式碼**
  - 改為統一走 MQTT publish 到 `home/vacuum_01/cmd`

- [ ] **「只說名字預設啟動」邏輯直接刪除**
  - 現況：`intent.py` 中 hardcode `if device.type == "vacuum"` 預設為 `on`
  - 決策：此邏輯違反設計一致性（落地燈需說動詞，掃地機不用，自相矛盾）
  - 作法：直接刪除，只說裝置名但無動詞 → 一律回傳 `unknown`，行為與所有裝置一致

---

## 完整依賴順序

```
Phase 1                          Phase 4-1
(Arduino ArduinoJson             (myxiaomi MQTT subscriber)
 + action_keywords payload)            ↓
      ↓                          Phase 4-2
Phase 2                          (myxiaomi Discovery 發布)
(server 動態建表)   ←────────────────────┘
      ↓
Phase 3
(intent.py per-device keywords)
      ↓
Phase 4-3
(dispatch.py 清理 HTTP 直呼叫)
```

- **Phase 1 & Phase 4-1** 可平行開發（互不依賴）
- **Phase 2** 需要 Phase 1 和 Phase 4-2 都完成（兩端 payload 格式定案）
- **Phase 3** 需要 Phase 2 完成後整合測試
- **Phase 4-3** 為最後清理，需要 Phase 3 完成確認系統正常後執行

---

## 附錄 A：現有 intent.py 快路徑架構

```
文字輸入
  ↓
extract_intent_from_text()（關鍵字快路徑）
  ├─ target + action 都命中 → 直接返回，跳過 LLM ✓
  ├─ 完全沒裝置名 → 直接 unknown，跳過 LLM ✓
  └─ 部分命中 → parse_intent_with_llm()（慢路徑）
       ↓ qwen2.5:0.5b via Ollama
       ├─ 結果有效 + 與關鍵字一致 → 用 LLM 結果
       ├─ 與關鍵字衝突 → 關鍵字優先（保守策略）✓
       └─ 解析失敗 → fallback 關鍵字 ✓
```

## 附錄 B：現有全域 ACTION_KEYWORDS（待 per-device 化）

```python
ACTION_KEYWORDS = {
    "on":  ["開", "打開", "開啟", "啟動", "掃地", "清掃", "開始",
            "turn on", "on", "open", "kaitan"],
    "off": ["關", "關閉", "關掉", "停止", "回充", "充電", "回去", "回家",
            "turn off", "off", "close", "kuan teng"],
}
```
> Phase 3 完成後，`"掃地"`, `"清掃"`, `"回充"`, `"回家"` 等 vacuum 專屬詞
> 應從全域移除，移至 `vacuum_01` 的 per-device keywords。

## 附錄 C：myxiaomi 現有 API 端點（供 Phase 4-1 MQTT bridge 參考）

- `POST /v1/devices/{id}/start` → 啟動全屋清掃
- `POST /v1/devices/{id}/home`  → 回充
- `POST /v1/devices/{id}/pause` → 暫停
- `GET  /v1/devices/{id}/status`→ 查詢狀態
- `GET  /v1/history/runs`       → 清掃歷史
- 分區清掃：`segment_clean` / `zoned_clean`（進階，不在本次範圍）

## 附錄 D：myxiaomi 排程與守門邏輯注意事項（Phase 4-1 開發參考）

| 機制 | 說明 | MQTT bridge 的影響 |
|---|---|---|
| active_runs | 追蹤進行中任務 | 語音觸發需寫入，否則守門無法正確識別 |
| 電量守護 | < 20% 拒絕啟動 | Bridge 需處理 controller 拋出的拒絕錯誤 |
| fallback guard (31分) | 防外部排程誤觸 | 有 active_runs 記錄時 guard 自動略過 ✓ |
| 衝突檢測 | cron 與語音同時觸發 | 遵循現有 est_duration 衝突邏輯 |
| 分區清掃 | zone_id 多種模式 | 本次只實作全屋 START，zone 留 Phase 5 |
