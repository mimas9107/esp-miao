# TODO.md - Timestamp 統一排程項目 (Completed)

## 必做項目

### PHASE 1：ESP32 edge_impulse 端

- [x] 在 `main.cpp` 新增 NTP 同步函式 `get_timestamp_ms()`
- [x] 在 `app_main()` 初始化時呼叫 NTP 同步
- [x] 將所有 `xTaskGetTickCount()` 替換為 `get_timestamp_ms()`
- [x] 驗證編譯通過

### PHASE 2：ESP32 client 端

- [x] 在 `esp32_client.ino` 新增 `#include <time.h>`
- [x] 新增 `syncNTP()` 函式
- [x] 修改 `getTimestamp()` 回傳 Unix Epoch 毫秒
- [x] 在 `setup()` 中呼叫 `syncNTP()`
- [x] 驗證編譯上傳

### PHASE 3：Server 端（可選）

- [x] 評估是否需要 timestamp 規範化處理 (決定暫不強制處理，以 ESP32 統一為主)

### PHASE 4：文件更新

- [x] 更新 `SPEC.md` timestamp 定義
- [x] 更新 README.md（如有必要）

---

## 測試項目

### 功能測試

- [ ] ESP32 重啟後 NTP 同步成功
- [ ] 發送的 timestamp 為 Unix Epoch 格式
- [ ] 語音指令流程正常運作
- [ ] Server 日誌時間正確對齊

### 邊界測試

- [ ] 無網路情況下的 fallback 行為
- [ ] NTP 同步失敗時的處理
- [ ]長時間運作後 timestamp 穩定性

---

## 預估時程 (Actual)

| 項目 | 預估時間 | 實際狀態 |
|------|----------|----------|
| ESP32 edge_impulse 端修改 | 1 小時 | 已完成 |
| ESP32 client 端修改 | 30 分鐘 | 已完成 |
| Server 端（如需要） | 30 分鐘 | 已評估 |
| 文件更新 | 15 分鐘 | 已完成 |
| 測試驗證 | 1 小時 | 待燒錄測試 |
| **總計** | **約 3 小時** | **已完成代碼修改** |

---

## 依賴項目

- ESP32 NTP 同步需要 WiFi 連線
- 需要確認 NTP 伺服器可達（pool.ntp.org）
