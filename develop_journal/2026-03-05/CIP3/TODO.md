# TODO.md - CIP3 實作排程（待啟動）

## PHASE 0：啟動前確認（Blocking）
- [ ] MAX98357A 到貨並完成接線
- [ ] 確認 ESP32 可用 GPIO 與 I2S pin map
- [ ] 確定提示音檔案（建議 200ms PCM mono 16k）

## PHASE 1：播放能力建立
- [ ] 在 `main/CMakeLists.txt` 加入 `EMBED_FILES`
- [ ] 在 `main.cpp` 增加音檔符號宣告與長度取得
- [ ] 新增 I2S TX 初始化與釋放流程
- [ ] 新增提示音播放函式（blocking 播放）

## PHASE 2：喚醒流程串接
- [ ] 在 wake word 命中點插入提示音播放
- [ ] 播放完成後加入 cooldown（預設 150ms）
- [ ] 再啟動既有 3 秒錄音流程
- [ ] 新增 suppression window（預設 1200ms）

## PHASE 3：穩定性與回歸
- [ ] 驗證喚醒->播放->錄音->上傳完整鏈路
- [ ] 驗證連續喚醒 30 次無卡死/重啟
- [ ] 驗證 WebSocket 斷線重連邏輯未回歸
- [ ] 驗證記憶體與 CPU 負載在可接受範圍

## PHASE 4：文件與交付
- [ ] 更新 `SPEC.md`（若新增裝置回饋行為需明確描述）
- [ ] 更新 develop_journal 測試紀錄
- [ ] 提交最終 REVIEW 結果

## 參數預設（首版）
- [ ] `ACK_DURATION_MS = 200`
- [ ] `ACK_COOLDOWN_MS = 150`
- [ ] `WAKE_SUPPRESSION_MS = 1200`
