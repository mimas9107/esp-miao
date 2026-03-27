# NOTES.md - CIP3 技術筆記（預研）

## 1. 現況程式觀察
- 現有 `main.cpp` 僅配置 I2S RX（INMP441），尚無 I2S TX 播放路徑
- 喚醒後流程為 LED 提示 -> 直接錄 3 秒 -> 傳送 WS
- Server `play` 訊息目前僅記錄 log，尚未實作本地播放

## 2. 實作原則
- 不改變系統角色分工：ESP32 不承擔意圖判斷與 MQTT 控制
- 播放邏輯應為本地 UI 回饋，不影響 ASR/LLM 主流程
- 先做簡單可靠版本，再考慮功能擴充（多音效、音量控制）

## 3. 音訊格式建議
- 優先：raw PCM，避免 WAV parser 複雜性
- 若使用 WAV：限制為固定規格（16k/16-bit/mono），只做最小 header 檢查

## 4. 可能踩雷
- 提示音回灌到 mic 造成錄音前段污染
- 播放與錄音切換時 DMA buffer 殘留
- 喚醒連發時，狀態機未鎖定造成重入

## 5. 調參建議
- 提示音長度：150~300ms
- 播放後冷卻：100~200ms
- suppression：1000~1500ms
- 全部參數以 `#define` 或 Kconfig 可調

## 6. 量測與觀察點
- 打印關鍵時間戳：wake hit、play start/end、rec start/end、send start/end
- 計算 `wake->rec_start` 延遲與整體 E2E 響應時間
- 觀察 false trigger 與 false reject 是否惡化
