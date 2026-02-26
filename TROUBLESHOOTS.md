# Troubleshooting - False Trigger Case (v0.3.1)

## 案例描述 (2026-02-26)
在 Raspberry Pi 4 (8G) 部署 `esp_miao` 服務後，觀察到 ESP32 有高機率誤觸發（尤其是安靜環境或某些環境人聲/音效）。
即使 VAD 過門檻，MFCC 仍可能誤判為喚醒詞 `heymiaomiao`，並錄音傳送至 RPi 辨識。

### 觀測現象
- **現象一**：錄音音檔聽起來是一片安靜，但 Edge Impulse 給出的信心分數高於門檻（e.g., 0.77, 0.715）。
- **現象二**：Whisper ASR 辨識結果為空字串，代表該音訊對人類與 ASR 來說並非有意義的語句。
- **原因分析**：
  1. **VAD 門檻太低**：原本的 `1000.0f` 在 INMP441 安靜環境下的底噪（Noise Floor）可能剛好達標。
  2. **模型門檻邊緣觸發**：Edge Impulse 模型的預設門檻 `0.7` 對於某些底噪的 MFCC 特徵過於靈敏。
  3. **模型對安靜底噪缺乏負樣本**：模型訓練時可能未包含足夠的「純背景底噪」作為 `Noise` 或 `Unknown` 類別。

## 修復與優化策略 (v0.3.1)

### 1. 強化攔截邏輯 (Multi-layer Defense)
- **韌體層 (Firmware Level)**：
  - 將 `EI_CLASSIFIER_THRESHOLD` 從 `0.7` 提升到 **`0.8`**。這過濾掉了之前觀測到的 `0.77` 和 `0.715` 的誤判。
  - 將 `VAD_THRESHOLD` 從 `1000.0` 提升到 **`2000.0`**。這確保了「一片安靜」的情況下，根本不會啟動分類器。
- **通訊協議層 (Protocol Level)**：
  - 新增 `confidence` 分數透傳。ESP32 將 Edge Impulse 的預測結果直接告訴 Server，方便 Server 依據分數做不同處置。
- **伺服器層 (Server Level)**：
  - **空值攔截**：若 Whisper 辨識結果為空字串，Server 直接判定為誤觸，不進行 LLM 意圖解析。
  - **日誌追蹤**：將信心分數納入音檔檔名（e.g., `conf0.85_recorded_...wav`），建立「誤觸樣本庫」。

### 2. 調校建議 (Calibration Guide)
- **觀察 RMS 數值**：透過 ESP32 的日誌 `Probable hit: Conf: 0.77, RMS: 1250.00` 來觀察環境背景底噪的 RMS。如果安靜時 RMS 接近 2000，則需繼續調高 `VAD_THRESHOLD`。
- **負樣本收集**：將 `src/esp_miao/audio/` 下所有信心分數高但實際上是誤觸的 `.wav` 檔，收集後上傳至 Edge Impulse 標記為 `Noise` 或 `Unknown` 重新訓練模型。

## 結論
透過調高 VAD 門檻與模型門檻的「雙重防護」，以及 Server 端的「空值過濾」，已大幅降低安靜環境下的誤觸機率。目前的設定（VAD=2000, Conf=0.8）在一般居家環境下應能提供穩定的喚醒體驗。
