
# WALKTHROUGH / TODO LIST

## ESP32 Side

* [x] Setup esp-idf / Arduino (firmware/esp32_client)
* [x] Configure I2S mic (INMP441, GPIO 32/25/33)
* [x] Implement local relay driver (GPIO 26 for light, 27 for fan, 2 for LED)
* [x] Implement JSON client (using cJSON for server command parsing)
* [x] Implement fallback sender (now audio streaming sender)
* [ ] Implement feedback player (placeholder only)

### Wake Word - Edge Impulse

* [x] 訓練 Edge Impulse MFCC 模型 (esp-miao-mfcc, ID: 905178)
* [x] I2S Stereo + 左聲道提取 (ESP32 V1 硬體相容)
* [x] APLL 時鐘提供穩定 16kHz 取樣
* [x] RMS VAD 能量閘 (threshold: 1000)
* [x] 連續滑動視窗推論 (1000ms window, 250ms slice × 4)
* [x] 喚醒詞偵測: "heymiaomiao" (threshold > 0.7)
* [x] LED 閃爍回饋 (GPIO 2)
* [x] 整合至 esp-miao 母專案 (firmware/esp32_edge_impulse/)
* [x] Build 驗證通過 (idf.py build)
* [x] **WiFi 連線與 WebSocket 客戶端功能**
* [x] **音訊串流傳輸 (Chunked Audio Streaming)**
* [x] **接收伺服器指令並控制 GPIO**

## Server Side

* [x] WebSocket server
* [x] Audio/text receiver (現在支援分塊音訊串流接收與組裝)
* [x] ASR pipeline (整合 faster-whisper, 強制中文辨識)
* [x] Ollama intent parser (Prompt 優化, 關鍵字後備機制強化)
* [x] Device table manager
* [x] Action router
* [x] Feedback audio API
* [x] Logging

## Protocol

* [x] Define schema (models.py - 新增 audio_start, audio_chunk)
* [x] Timeout handling
* [x] Retry logic (retry.py)

## Safety

* [x] GPIO whitelist
* [x] Action validation
* [x] Fail-safe default off

## Testing & Tools

* [x] ESP32 Simulator (esp32-sim) - 支援 audio_request
* [x] Communication Test (tests/test_communication.py)
* [x] Audio Request (ASR) 流程測試 (tests/test_audio.py)
