# 2026-03-08 重構審查清單 (REVIEW_TODO.md)

## 1. 架構完整性 (Architectural Integrity)
- [x] 1. 確保所有 `from . import xxx` 的循環引用風險已排除。 (已透過 grep 掃描匯入關係，路徑清晰)
- [x] 2. 檢查 `app.py` 中 `handle_*` 函式是否需要更進一步的異步優化。 (已改為非阻塞背景執行)
- [ ] 3. 確認 `config.py` 中的 `inference_executor` 在多模型載入下的 CPU 分配情形。 (待多模型上線後持續觀察)

## 2. 版本一致性 (Version Consistency)
- [x] 1. 確認 `version.py`, `pyproject.toml`, `CHANGELOG.md` 三方一致。 (皆為 v0.5.1)
- [x] 2. 驗證根路由 `/` 的 JSON 輸出是否正確反應當前版號。 (已透過 curl 測試通過)

## 3. 測試覆蓋 (Testing)
- [x] 1. 確認所有整合測試 (`tests/test_integrated_modular.py`) 已包含 WebSocket 握手失敗的異常處理。 (已包含 mock 測試)
- [x] 2. 針對 `dispatch.py` 中的 HTTP API 部份，建立更多針對 `vacuum` 的 Mock 測試場景。 (已在單元測試中覆蓋)
