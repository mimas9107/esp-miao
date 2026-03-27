# esp-miao-test2 VAD 改進測試記錄

## 測試日期
2026-03-03

## 改進概述

本次測試針對 esp-miao 的 VAD (Voice Activity Detection) 機制進行優化，將原本簡單的 RMS 能量閾值方法改為 FFT 頻域能量分析。

## 技術細節

### 1. 舊方法 (RMS)
- **原理**: 計算音訊的均方根 (RMS) 值
- **閾值**: 1500
- **問題**: 
  - 距離遠近對音量影響很大
  - 無法區分人聲與環境噪音

### 2. 新方法 (FFT)
- **原理**: 計算 300Hz ~ 3400Hz 人聲頻段內的能量
- **FFT Size**: 512
- **閾值**: 23000 ~ 28000 (測試可用範圍)
- **優點**:
  - 距離遠近對偵測影響變小
  - 可過濾非人聲頻率的噪音

### 3. 實作細節

```c
// FFT 參數
#define FFT_SIZE            512
#define FFT_FREQ_MIN        300   // Hz
#define FFT_FREQ_MAX        3400  // Hz
#define FFT_ENERGY_THRESHOLD 25000 // 可調範圍 23000-28000
```

### 4. 測試結果

| 狀態 | RMS 值 | FFT 能量 |
|------|--------|----------|
| 安靜時 | ~500-600 | ~4500-6000 |
| 說話時 | ~2200-2700 | ~63000-73000 |

**結論**: FFT 方法在遠場識別時更穩定，距離變化對偵測結果影響較小。

## 配置說明

修改 `~/projects/esp-miao-test2/firmware/esp32_edge_impulse/main/main.cpp` 中的參數：

```c
#define FFT_ENERGY_THRESHOLD 25000  // 閾值，可根據環境調整
```

## 待辦事項

- [ ] 合併回母專案 esp-miao
- [ ] 進一步調優閾值
- [ ] 加入自適應閾值機制
