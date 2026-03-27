# 待辦事項 (TODO.md)

## 合併前準備

- [x] 在 esp-miao-test2 完成 VAD 改進
- [x] 測試 FFT VAD 方法穩定性
- [x] 記錄測試結果 (TEST_NOTES.md)
- [x] 撰寫合併計畫 (PLAN.md)

## 合併執行

- [x] 分析來源 ~/projects/esp-miao-test2/firmware/esp32_edge_impulse/main/main.cpp 中的 FFT VAD程式碼,
- [x] 準備整合到母專案, 分析 ~/projects/esp-miao/firmware/esp32_edge_impulse/main/main.cpp程式碼,
- [x] 更新母專案的 VAD參數與 FFT VAD參數
- [x] 整合程式碼入母專案
- [x] 確保編譯通過
- [x] 在母專案硬體上測試

## 合併後優化

- [ ] 優化 FFT 計算效能
- [ ] 根據不同環境進一步調優 FFT 閾值

## 備註

- 測試確定的閾值範圍: 23000-28000
- 預設建議值: 25000
