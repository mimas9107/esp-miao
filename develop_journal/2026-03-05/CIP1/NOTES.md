# NOTES.md - Timestamp 統一技術重點與實測紀錄

## 1. 核心技術總結
### 1.1 Miao-Sync 協議 (WebSocket 時間同步)
- **背景**: ESP32 NTP 同步常受限於網路環境或外網可達性。
- **方案**: 實作了「握手即同步」機制。當裝置連線至 WebSocket 時，Server 主動發送 `time_sync` 訊息（Unix Epoch）。
- **效果**: ESP32 接收後立即使用 `settimeofday` 校正系統時鐘，達成離線環境下的全域時間對齊。

### 1.2 雙重日誌透明度
- 在 ESP32 所有關鍵動作（發送音訊、執行動作、設定 GPIO）中加入 `[TS: %llu]`。
- Server 端接收訊息時同步輸出 `Device TS`。
- **效益**: 可精確計算端到端延遲 (End-to-End Latency)。

---

## 2. 實測數據紀錄 (2026-03-05)

### 2.1 修改前 (Baseline)
- ESP32 TS: `(58141)` (開機毫秒)
- Server TS: `1709366400000` (Unix 毫秒)
- 缺點: 無法比對兩端日誌，無法計算網路/推論延遲。

### 2.2 修改後 (Optimized)
**ESP32 端輸出片段:**
```
>>> WAV: Sending 48000 samples via WebSocket (Binary) at TS: 1772681422173...
I (142585) ESP-MIAO: [TS: 1772681424703] Executing Action: relay_set on light -> on
```
**Server 端輸出片段:**
```
2026-03-05 11:31:05,714 [INFO] esp-miao: Stream start: esp32_01 mode=binary, total=48000
...
2026-03-05 11:31:06,416 [INFO] esp-miao: MQTT Publish: [lamp/command] -> ON (for light)
```

### 2.3 分析結論
- **網路延遲**: 從 ESP32 發送結束到 Server 完成 ASR 與 MQTT 發佈，整體響應感極佳。
- **日誌一致性**: 兩端 TS 數據完全吻合，成功消弭了 1970 年初始值與現實時間的斷層。

---

## 3. 驗證清單
- [x] WebSocket 連線即同步
- [x] 所有 ESP_LOGI 包含 Timestamp
- [x] SPEC.md 定義更新
- [x] Arduino Client 同步機制實作
