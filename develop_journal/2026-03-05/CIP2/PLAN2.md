# PLAN2.md - Metrics 系統實作計畫

## 專案背景
本專案為 ESP32 智慧語音控制系統，採用 RPi4 + faster-whisper + rule-first + LLM fallback + MQTT dispatch 架構。

## 設計目標（來自 Metrics-PLAN.md）
- **硬限制**: RPi4 CPU 已忙碌，不可明顯增加延遲，不可引入重量級依賴
- **軟目標**: 能量化系統行為、統計 fallback 比例、分析 latency 分布、分析錯誤類型、能離線分析

---

## 核心 Metrics 模組設計

### 1. 檔案結構
```
src/esp_miao/
    metrics/
        __init__.py
        context.py    # MetricsContext（每請求一個）
        aggregator.py # MetricsAggregator（全域）
        logger.py     # Async JSONL Writer
```

### 2. MetricsContext（每請求一個）
```python
class MetricsContext:
    def __init__(self, request_id: str):
        self.request_id = request_id
        self.start_time = time.time()
        self.data: dict = {}
    
    def mark_stage(self, name: str, value: Any): ...
    def set_flag(self, key: str, value: bool): ...
    def record_latency(self, key: str, seconds: float): ...
    def finalize(self) -> dict: ...
```

### 3. MetricsAggregator（全域）
```python
class MetricsAggregator:
    def __init__(self):
        self.total_requests = 0
        self.llm_calls = 0
        self.llm_success = 0
        self.keyword_success = 0
        self.total_latency = 0.0
        self.asr_total_latency = 0.0
        self.errors = 0
    
    def record(self, context: MetricsContext): ...
    def snapshot(self) -> dict: ...
```

### 4. JSONL Writer（非同步）
- 使用 `queue.Queue` + background thread
- append-only 寫入
- flush interval: 1~2 秒

---

## 插入點對照表

| 階段 | 函式位置 | 紀錄欄位 |
|------|----------|----------|
| 1. WebSocket 收到音訊 | `handle_audio_request`, `process_complete_audio` | `request_id`, `start_timestamp` |
| 2. ASR 完成 | `transcribe_audio` | `asr_latency`, `asr_text_length`, `asr_empty` |
| 3. Keyword Intent 解析 | `extract_intent_from_text` | `keyword_action_found`, `keyword_target_found` |
| 4. LLM 呼叫 | `parse_intent_with_llm` | `llm_called`, `llm_latency`, `llm_success` |
| 5. Validator | `action_validator.validate` | `validator_pass`, `reject_reason` |
| 6. Dispatch | `dispatch_command` | `dispatch_type`, `dispatch_success` |
| 7. Request 結束 | `process_complete_audio` return 前 | `total_latency`, flush JSONL |

---

## JSONL 輸出格式
```json
{
  "timestamp": 1710000000,
  "request_id": "device_001_1234567890",
  "asr_latency": 0.82,
  "asr_text_length": 12,
  "asr_empty": false,
  "keyword_action_found": true,
  "keyword_target_found": true,
  "llm_called": true,
  "llm_latency": 0.41,
  "llm_success": true,
  "validator_pass": true,
  "reject_reason": null,
  "dispatch_type": "mqtt",
  "dispatch_success": true,
  "final_action": "relay_set",
  "final_target": "light01",
  "final_value": "on",
  "total_latency": 1.34,
  "error_type": null
}
```

---

## PHASE 1：基礎框架(寫入NOTES.md 項目起始時間,項目完成時間)

1. 建立 `metrics/` 目錄與 `__init__.py`
2. 實作 `MetricsContext` 類別
3. 實作 `MetricsAggregator` 類別（thread-safe）
4. 實作 async JSONL writer
5. 建立單元測試（模擬 1000 次 request）

**驗收條件**：
- 不拋例外
- CPU 使用 < 3%
- 無 blocking

---

## PHASE 2：插入至主流程(寫入NOTES.md 項目起始時間,項目完成時間)

1. 在 `handle_audio_request` / `process_complete_audio` 建立 context
2. 在 `transcribe_audio` 結束後記錄 ASR latency
3. 在 `extract_intent_from_text` 回傳時記錄關鍵字命中
4. 在 `parse_intent_with_llm` 記錄 LLM 呼叫與 latency
5. 在 `action_validator.validate` 記錄驗證結果
6. 在 `dispatch_command` 記錄 dispatch 結果
7. 在 request 結束時計算 total_latency 並 flush JSONL

**驗收條件**：
- log file 正確生成
- 不影響語音流程

---

## PHASE 3：分析工具(寫入NOTES.md 項目起始時間,項目完成時間)

新增 `scripts/analyze_metrics.py`：
- 平均 ASR latency
- LLM fallback ratio
- LLM success rate
- 平均 total latency
- 錯誤類型分布

---

## 設計決策(堅持原則)
1. **metrics 不能影響主流程**：使用 context object 傳遞，不在業務邏輯中混入 metrics
2. **不可同步寫檔**：使用 queue + background thread
3. **不可在 ASR loop 裡做重運算**：只記錄時間戳，不做額外處理
4. **不可引入大型依賴**：只用標準庫 + threading
5. **context 必須 request-scoped**：每個 request 獨立 context
