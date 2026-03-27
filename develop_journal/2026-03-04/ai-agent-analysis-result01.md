## ESP‑MIAO Server CPU 使用情況分析
（依據 `ps.log` 中 PID **16107** 的 35 % CPU 佔用）

| 項目 | 位置 | 為何可能佔用大量 CPU |
|------|------|----------------------|
| **Whisper ASR** | `transcribe_audio()`（第 328‑401 行） | `whisper_model.transcribe()` 會在 CPU 上執行完整的語音辨識。即使使用 `device="cpu"`、`compute_type="int8"`，仍會跑 **beam search**（`beam_size=3`）以及語言偵測、噪聲過濾等步驟。每一次完整音訊（約 3 秒 PCM）都會觸發一次 **阻塞式** 推論，透過 `asyncio.to_thread` 轉到子執行緒，但子執行緒仍會佔用 CPU。若客戶端持續送音訊（例如持續開啟 VAD），CPU 會被頻繁佔滿。 |
| **LLM Intent Parsing** | `parse_intent_with_llm()`（第 445‑504 行） | 呼叫 `ollama.generate(model="qwen2.5:0.5b", …)` 會在本機 **Ollama 服務**（PID 1674）上執行 LLM 推論。即使模型只有 0.5 B 參數，仍是 **CPU‑only** 推論，會消耗相當的算力。若關鍵字匹配失敗或使用者語句較長，LLM 會被觸發，導致額外的 CPU 負載。 |
| **音訊檔案寫入** | `save_audio_file()`（第 660‑688 行） | 每一次完整音訊都會在背景執行緒中寫入 WAV 檔案。大量 I/O（尤其是磁碟寫入）會產生 **上下文切換**，在 CPU‑bound 的 Whisper/LLM 推論同時進行時，會加劇 CPU 使用率。 |
| **WebSocket 迴圈** | `websocket_endpoint()`（第 909‑986 行） | 迴圈本身是 `await websocket.receive()`，不會造成忙等。但若客戶端持續發送 **binary/base64** 小片段且 `is_last` 為 `True` 的頻率過高，會導致 **process_stream_end → process_complete_audio** 被頻繁觸發，間接放大上面的兩個 CPU 重點。 |
| **MQTT 客戶端** | `publish_mqtt_command()`（第 181‑202 行） | MQTT 發佈本身開銷極低，對 CPU 影響可忽略。 |

### 為什麼 CPU 會長時間維持在 35 %？
- **單執行緒的推論**：`whisper_model.transcribe()` 與 `ollama.generate()` 都是 **單執行緒**、CPU‑bound 的工作。即使使用 `asyncio.to_thread`，仍只佔用一個 CPU 核心（約 35 % 在 8‑core 系統上）。若同時有多個音訊請求，會產生多個子執行緒，CPU 使用率會快速飆升。  
- **持續的音訊流**：ESP32 端在偵測到喚醒詞後會持續傳送 3 秒音訊，若使用者說話頻繁或測試腳本自動重複觸發，伺服器會不斷進入 `process_complete_audio` → **ASR** → **LLM** 的完整流程。  
- **LLM 呼叫未被關鍵字過濾**：雖然有「Priority Logic」先做關鍵字匹配，但在多語言或口音不佳的情況下，關鍵字匹配失敗率會提升，導致每一次都必須走 LLM，進一步加重 CPU。 

## 改善方向（可直接在程式碼層面調整）

| 類別 | 建議 | 影響 |
|------|------|------|
| **Whisper** | 1. **降低 beam_size**（例如 1）或改用 `best_of=1`。<br>2. 使用更小的模型（`tiny`、`base` 已在使用，但可改為 `tiny`）。<br>3. 若硬體允許，可改為 **GPU**（`device="cuda"`）或 **OpenVINO**/`torch.compile` 加速。 | 大幅減少每次 ASR 的 CPU 時間，可能略微降低辨識準確度。 |
| **LLM** | 1. **先檢查關鍵字**，若匹配成功直接返回（已有，但可把 `if keyword_intent["action"] != "unknown"` 判斷提前到 `parse_intent_with_llm` 前，避免不必要的 `ollama.generate` 呼叫）。<br>2. 為常見指令建立 **本地快取**（例如 `{"開燈": {"action":"relay_set","target":"light","value":"on"}}`），直接返回快取結果。<br>3. 若仍需要 LLM，改用 **更輕量的模型**（如 `phi3:mini`）或在 Ollama 端啟用 **GPU**。 | 減少 LLM 推論次數與時間，降低 CPU 負載。 |
| **音訊儲存** | 改為 **非同步寫入**（`aiofiles`）或僅在除錯模式下寫檔。可加入環境變數 `DEBUG_AUDIO_SAVE=0` 讓正式運行時跳過磁碟 I/O。 | 減少 I/O 產生的上下文切換與 CPU 佔用。 |
| **WebSocket** | 1. 在 `audio_chunk` 處理時，若 `is_last` 為 `False`，僅 **累積** 並不做任何 CPU 密集工作。<br>2. 加入 **速率限制**（例如每秒最多處理一次完整音訊）以防止惡意或測試腳本的過度呼叫。 | 防止短時間內大量觸發完整流程。 |
| **多執行緒/併發** | 使用 **`concurrent.futures.ThreadPoolExecutor(max_workers=N)`**，限制同時執行的 ASR/LLM 任務數量（例如 `N=2`），避免 CPU 被過度飽和。 | 控制同時推論數量，讓 CPU 使用率更平穩。 |
| **監控** | 在 `process_complete_audio` 前後加入 **計時**（`time.perf_counter()`），將每階段耗時寫入日誌，方便定位哪一步最耗時。 | 讓日後調校更有依據。 |

### 範例：在 `parse_intent_with_llm` 前快速返回關鍵字結果
```python
def parse_intent_with_llm(text: str) -> dict:
    # 先做關鍵字匹配，若成功直接返回，避免 LLM 呼叫
    keyword_intent = extract_intent_from_text(text)
    logger.debug(f"Keyword extraction: {text} -> {keyword_intent}")

    if keyword_intent["action"] != "unknown" and keyword_intent["target"] in [
        d.name for d in device_table.devices
    ]:
        logger.info(f"Keyword match, skip LLM for '{text}'")
        return keyword_intent

    # 只有在關鍵字無法確定時才走 LLM
    ...
```

### 範例：限制同時推論的執行緒數
```python
from concurrent.futures import ThreadPoolExecutor

# 在模組層級建立全域執行緒池（只建立一次）
executor = ThreadPoolExecutor(max_workers=2)   # 依 CPU 核心數調整

async def transcribe_audio(...):
    ...
    # 使用 executor 取代 asyncio.to_thread
    text, info = await asyncio.get_event_loop().run_in_executor(
        executor, run_transcription
    )
    ...
```

### 範例：可選的音訊儲存開關
```python
DEBUG_AUDIO_SAVE = os.getenv("DEBUG_AUDIO_SAVE", "1") == "1"

async def process_complete_audio(...):
    ...
    if DEBUG_AUDIO_SAVE:
        asyncio.create_task(asyncio.to_thread(save_audio_file))
    ...
```

## 結論
- **CPU 高佔用的根本原因**：每一次完整音訊都會觸發 **Whisper ASR**（CPU‑intensive）以及 **Ollama LLM**（CPU‑intensive）兩個階段。  
- **最直接的降載手段**：  
  1. **減少或避免 LLM 呼叫**（關鍵字快取、提前返回）。  
  2. **降低 Whisper 推論負荷**（減小 `beam_size`、使用更小模型或改用 GPU）。  
  3. **限制同時推論數量**（ThreadPoolExecutor）。  
  4. **關閉除錯時的音訊寫檔**。  
- 以上調整均可在不改變功能前提下顯著降低伺服器的 CPU 使用率，讓 ESP‑MIAO 在長時間運行時更穩定。