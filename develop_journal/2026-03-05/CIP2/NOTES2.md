# CIP2 技術重點筆記：Metrics 分析與硬體評比

## 1. 實驗工具組介紹

### 1.1 互動式實驗導引 (`scripts/run_interactive_bench.py`)
為了確保實驗數據具備「真實物理環境」的參考價值，此腳本採分關卡引導模式：
- **第 1 關**：物理基準測試（安靜環境）。
- **第 2 關**：環境雜音魯棒性測試（模擬真實生活噪音）。
- **第 3 關**：意圖解析邏輯測試（驗證關鍵字攔截 vs LLM 耗時）。
- **第 4 關**：併發壓力測試（使用模擬器快速發送多個請求）。

**用法**：
```bash
uv run python scripts/run_interactive_bench.py
```

### 1.2 雙環境對比分析工具 (`scripts/analyze_metrics.py`)
支援單一環境分析與雙環境（如 PC vs RPi4）並排對比。

**單一環境分析**：
```bash
uv run python scripts/analyze_metrics.py metrics.jsonl
```

**雙環境硬體評比**：
```bash
uv run python scripts/analyze_metrics.py metrics_pc.jsonl metrics_rpi4.jsonl
```

---

## 2. 硬體基準對比 (PC vs RPi4) 實驗流程

為了獲得最具參考價值的數據，建議遵循以下「變因控制」流程：

1.  **PC 實驗**：
    - 在開發機執行 `run_interactive_bench.py`。
    - 獲得 `metrics.jsonl` 後更名為 `metrics_pc.jsonl`。
2.  **RPi4 實驗**：
    - 將程式碼同步至 RPi4（確保版本一致）。
    - 執行 `run_interactive_bench.py`。
    - 獲得 `metrics.jsonl` 後更名為 `metrics_rpi4.jsonl`。
3.  **綜合評比**：
    - 使用 `analyze_metrics.py` 同時傳入兩個檔案。
    - 重點觀察 `Avg ASR Latency` 與 `Summary` 中的效能倍率（Slowdown ratio）。

---

## 3. 關鍵量測指標定義

| 指標 | 定義 | 最佳化方向 |
| :--- | :--- | :--- |
| **ASR Latency** | Whisper 模型處理音訊的純運算時間。 | 更換模型類型（tiny/base）、硬體加速。 |
| **LLM Latency** | Ollama 產生 JSON 意圖的時間。 | 增加關鍵字規則以減少 LLM 呼叫。 |
| **Total Latency** | 從 WebSocket 收到音訊到發出 MQTT/API 指令的總時長。 | 整體系統流程優化。 |
| **Keyword Hit Rate** | 關鍵字成功攔截請求的比例。 | 擴充 `Device.aliases`。 |
| **Error Rate** | 發生逾時、解析失敗或硬體錯誤的頻率。 | 網路穩定性、模型魯棒性。 |

---

## 4. 設計決策紀錄
- **非侵入式設計**：不修改核心程式碼來判斷主機名稱，改由分析工具進行外部對比，保持生產環境代碼純淨。
- **非同步日誌**：使用專屬執行緒寫入 `jsonl`，確保 RPi4 在高負載下不會因為磁碟 I/O 阻塞而影響語音辨識的準確度。
