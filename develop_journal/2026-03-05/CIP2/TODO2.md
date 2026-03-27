# TODO2.md - Metrics 系統實作清單 (Completed)

## 必做項目

### PHASE 1：基礎框架 (Completed)

- [x] 建立 `src/esp_miao/metrics/` 目錄
- [x] 建立 `src/esp_miao/metrics/__init__.py`
- [x] 實作 `context.py` - MetricsContext 類別
- [x] 實作 `aggregator.py` - MetricsAggregator 類別
- [x] 實作 `logger.py` - Async JSONL Writer (thread-safe, non-blocking)

### PHASE 2：插入至主流程 (Completed)

- [x] 在 `server.py` 匯入 metrics 模組
- [x] 修改 `handle_audio_request` / `process_complete_audio` - 建立 MetricsContext
- [x] 插入各階段 metrics:
  - [x] ASR latency
  - [x] Keyword hit
  - [x] LLM latency
  - [x] Dispatch type/success
  - [x] Total latency & flush
- [x] 修改 `dispatch_command` 簽名以傳遞 context

### PHASE 3：分析工具 (Completed)

- [x] 建立 `scripts/analyze_metrics.py`
  - [x] 支援 latency 統計
  - [x] 支援邏輯分支 (LLM vs Keyword) 統計
  - [x] 支援派發類型統計

---

## 預期效益
- **可觀測性**: 終於能看見 RPi4 上的實際推論耗時分布。
- **優化依據**: 未來若要升級模型 (tiny -> base) 或調整 prompt，有數據可供 A/B 測試。
