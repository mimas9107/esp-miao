# TEST_REVIEW_TODO.md - Timestamp 統一測試結果審查

## 測試項目清單

### 1. NTP 同步測試

- [ ] **ESP32 edge_impulse 端**
  - [ ] WiFi 連線後 NTP 同步成功
  - [ ] Serial log 顯示同步時間
  - [ ] 同步失敗時有適當處理

- [ ] **ESP32 client 端**
  - [ ] WiFi 連線後 NTP 同步成功
  - [ ] Serial monitor 顯示同步時間
  - [ ] 同步失敗時有適當處理

### 2. Timestamp 格式測試

- [ ] **ESP32 發送的訊息**
  - [ ] timestamp 為 Unix Epoch 毫秒格式
  - [ ] 格式範例：`1741158600000`（約 2026-03-05 14:30:00 UTC+8）

- [ ] **Server 接收的訊息**
  - [ ] 可正確解析 timestamp
  - [ ] 與 Server 本地時間誤差 < 5 秒

### 3. 功能回歸測試

- [ ] **語音指令流程**
  - [ ] 喚醒詞偵測正常
  - [ ] 音訊傳輸正常
  - [ ] ASR 辨識正常
  - [ ] LLM 解析正常
  - [ ] MQTT 指令發送正常

- [ ] **回饋音效**
  - [ ] 成功音效播放正常
  - [ ] 失敗音效播放正常

### 4. 邊界情況測試

- [ ] **網路異常**
  - [ ] WiFi 斷開後重連正常
  - [ ] NTP 同步失敗時不阻塞開機

- [ ] **長時間運作**
  - [ ] 執行 1 小時後 timestamp 仍正確
  - [ ] 無記憶體洩漏

### 5. 日誌對齊測試

- [ ] **時間戳記比對**
  - [ ] ESP32 訊息 timestamp 與 Server 接收時間對齊
  - [ ] 日誌分析工具能正確解析

---

## 審查檢查點

### P0 - 必要條件

- [ ] ESP32 能成功編譯燒錄
- [ ] NTP 同步成功
- [ ] timestamp 為 Unix Epoch 毫秒
- [ ] 語音指令功能正常

### P1 - 重要條件

- [ ] NTP 失敗時有 fallback
- [ ] 日誌時間正確對齊
- [ ] 邊界情況處理正確

### P2 - 優化條件

- [ ] Serial log 資訊完整
- [ ] 錯誤訊息清楚易懂

---

## 驗收簽核

| 項目 | 結果 | 簽署 |
|------|------|------|
| NTP 同步測試 | [ ] Pass [ ] Fail | |
| Timestamp 格式測試 | [ ] Pass [ ] Fail | |
| 功能回歸測試 | [ ] Pass [ ] Fail | |
| 邊界情況測試 | [ ] Pass [ ] Fail | |
| 日誌對齊測試 | [ ] Pass [ ] Fail | |

---

## 測試後預期成果

1. **所有 timestamp 統一為 Unix Epoch 毫秒**
2. **日誌時間能正確對齊**
3. **可計算 end-to-end latency**
4. **未來 Metrics 系統能正確運作**
