# 合併計畫 (PLAN.md)

## 目標
將 esp-miao-test2 的 VAD 改進合併回母專案 esp-miao/

## 改動範圍

### 1. 程式碼變更
- **來源檔案**: `~/projects/esp-miao-test2/firmware/esp32_edge_impulse/main/main.cpp`
- **目標檔案**: `~/projects/esp-miao/firmware/esp32_edge_impulse/main/main.cpp`
- **變更**:
  - 新增 FFT VAD 方法 (vad_fft_compute, vad_new_fft_detect)
  - 移除舊的 RMS 僅做比較用程式碼
  - 更新 VAD 閾值參數

### 2. 參數調整
```c
// 新增參數
#define FFT_SIZE            512
#define FFT_FREQ_MIN        300   // Hz
#define FFT_FREQ_MAX        3400  // Hz
#define FFT_ENERGY_THRESHOLD 25000 // 可調
```

### 3. 測試記錄
- 參考 TEST_NOTES.md 中的測試結果
- 確認閾值可用範圍: 23000-28000

## 合併策略

1. **直接替換**: 將 main.cpp 中的 VAD 相關程式碼替換
2. **參數預設**: 使用測試過的預設值 25000
3. **保持相容**: 不影響現有 ML 模型與 WebSocket 功能

## 預期效益

- 遠場識別更穩定
- 對環境噪音的抵抗力提升
- 距離變化對偵測影響降低
