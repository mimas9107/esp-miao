# Troubleshooting - False Trigger Case (v0.3.1)

## 案例描述 (2026-02-26) - 續：Whisper 幻聽問題
在環境極度安靜時，除了 Edge Impulse 可能誤判外，Whisper ASR 有時會產生「重複性短語」的幻聽（Hallucination）。

### 觀測現象
- **現象**：ESP32 給出極高信心分數 (e.g., 0.895)，且 Whisper 辨識出「我认识了我认识了」等重複字句，導致系統誤啟動。
- **原因分析**：
  1. **Whisper 序列生成特性**：當音訊能量極低但有規律底噪時，模型會嘗試強行輸出文字，並陷入循環。
  2. **模型敏感度**：0.895 的信心分數代表環境底噪與喚醒詞特徵高度重疊。

## 修復與優化策略 (v0.3.2)
- **ASR 層 (ASR Level)**：
  - 加入 `no_speech_threshold=0.6`，讓 Whisper 自動過濾無聲片段。
  - 實作 **「重複性過濾 (Repetitive Filter)」**：若片段的 `no_speech_prob` 偏高且文字內容呈現重複模式（如前後半段相同），則予以攔截。
- **韌體層 (Firmware Level)**：
  - 將 `EI_CLASSIFIER_THRESHOLD` 進一步提升至 **`0.9`**。

## 調校建議 (Calibration Guide)
- **環境底噪分析**：如果 0.9 門檻仍無法擋住安靜時的誤觸，請務必將該音檔（Server 已自動存檔）下載並上傳至 Edge Impulse 作為 `Noise` 類別重新訓練。

## 結論
透過調高 VAD 門檻與模型門檻的「雙重防護」，以及 Server 端的「空值過濾」，已大幅降低安靜環境下的誤觸機率。目前的設定（VAD=2000, Conf=0.8）在一般居家環境下應能提供穩定的喚醒體驗。
