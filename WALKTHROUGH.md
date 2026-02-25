
# WALKTHROUGH / TODO LIST

## ESP32 Side

* [x] Setup esp-idf / Arduino (firmware/esp32_client)
* [x] Configure I2S mic (INMP441, GPIO 32/25/33)
* [x] Implement local relay driver
* [x] Implement JSON client
* [x] Implement fallback sender
* [ ] Implement feedback player (placeholder only)

### Wake Word - Edge Impulse (取代 esp-sr)

* [x] 訓練 Edge Impulse MFCC 模型 (esp-miao-mfcc, ID: 905178)
* [x] I2S Stereo + 左聲道提取 (ESP32 V1 硬體相容)
* [x] APLL 時鐘提供穩定 16kHz 取樣
* [x] RMS VAD 能量閘 (threshold: 1000)
* [x] 連續滑動視窗推論 (1000ms window, 250ms slice × 4)
* [x] 喚醒詞偵測: "heymiaomiao" (threshold > 0.7)
* [x] LED 閃爍回饋 (GPIO 2)
* [x] 整合至 esp-miao 母專案 (firmware/esp32_edge_impulse/)
* [x] Build 驗證通過 (idf.py build)

### Wake Word - esp-sr (原始規劃，已放棄)

* [ ] ~~Integrate esp-sr~~
* [ ] ~~Enable WakeNet~~
* [ ] ~~Configure MultiNet commands~~

> 注意: esp-sr 在標準 ESP32-WROOM (無 PSRAM) 上記憶體不足，
> 已改用 Edge Impulse TFLite 方案取代。

## Server Side

* [x] WebSocket server
* [x] Audio/text receiver
* [x] ASR pipeline (placeholder - integrate Whisper)
* [x] Ollama intent parser
* [x] Device table manager
* [x] Action router
* [x] Feedback audio API
* [x] Logging

## Protocol

* [x] Define schema (models.py)
* [x] Timeout handling
* [x] Retry logic (retry.py)

## Safety

* [x] GPIO whitelist
* [x] Action validation
* [x] Fail-safe default off
