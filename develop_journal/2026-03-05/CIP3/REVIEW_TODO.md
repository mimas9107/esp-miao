# REVIEW_TODO.md - CIP3 測試與審查清單

## P0 必要驗收
- [ ] 喚醒詞命中後可播放提示音
- [ ] 提示音後可正常錄滿 3 秒
- [ ] 3 秒音訊可成功上傳至 Server 並被處理
- [ ] 主流程無死鎖、無重啟

## P1 功能品質
- [ ] 連續 30 次喚醒測試成功率 >= 95%
- [ ] suppression window 生效（避免連續重複觸發）
- [ ] 播放後錄音首段污染可接受（可聽檢或波形檢查）
- [ ] WebSocket 緊急重連流程未受影響

## P2 穩定性與資源
- [ ] `idf.py size` 顯示 image 增量在預期內
- [ ] DRAM/IRAM 使用率未出現異常飆升
- [ ] 長時運行（>= 30 分鐘）無明顯 memory leak

## 回歸檢查
- [ ] 原有喚醒準確率未明顯下降
- [ ] 原有 LED 提示與 GPIO action 功能正常
- [ ] binary/base64 兩種傳輸模式至少驗證一種主路徑

## 問題紀錄欄
- [ ] Issue #1：
- [ ] Issue #2：
- [ ] Issue #3：

## 最終簽核
- [ ] Ready to implement（硬體與規劃條件俱備）
- [ ] Ready to merge（功能完成且測試通過）
