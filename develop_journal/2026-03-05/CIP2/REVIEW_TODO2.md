# REVIEW_TODO2.md - Metrics 系統檢閱清單

## 檢閱項目

### 1. 架構檢閱
- [ ] metrics 模組是否獨立於業務邏輯？
- [ ] 是否使用 context object 傳遞而非侵入式？
- [ ] 是否使用非同步寫入（queue + thread）？
- [ ] 是否有 flush interval 機制？

### 2. 效能檢閱
- [ ] CPU 使用是否 < 3%？（壓力測試驗證）
- [ ] 是否阻塞主線程？（需確認無 sync I/O）
- [ ] 記憶體成長是否穩定？（無 memory leak）

### 3. 資料完整性檢閱
- [ ] 每筆 request 是否都有對應的 JSONL 紀錄？
- [ ] 所有插入點是否都有正確紀錄？
- [ ] crash 後資料是否不遺失？（append-only 驗證）

### 4. 功能檢閱
- [ ] ASR latency 是否正確計算？
- [ ] LLM fallback ratio 是否可統計？
- [ ] keyword 命中率是否可統計？
- [ ] total latency 是否正確計算？

---

## 當這套 Metrics 上線後你能回答的問題

- LLM 真的有用嗎？
- fallback 佔幾 %？
- Whisper base 是否瓶頸？
- end-to-end latency 有沒有超過 1.5 秒？
- 哪種指令最容易失敗？

---

## 數據驅動決策依據

上線後你可以用數據決定：
- 要不要升級模型
- 要不要改 alias
- 要不要砍掉 LLM
- 要不要升級硬體

這才是真正有效有依據的架構優化。
