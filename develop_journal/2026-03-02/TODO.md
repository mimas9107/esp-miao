# 2026-03-02 任務清單

## 核心重構
- [x] 實作 DynamicDeviceTable 支援動態註冊
- [x] 建立 home/discovery 監聽機制
- [x] 重構 parse_intent_with_llm (關鍵字優先攔截)
- [x] ASR 流程記憶體化 (io.BytesIO)
- [x] 將 Whisper 推論移至非同步執行緒 (asyncio.to_thread)

## Bug 修復
- [x] 修正 Pydantic GPIO 驗證錯誤 (GPIO -1)
- [x] 修正 MQTT Topic Fallback 失敗問題
- [x] 解決靜態裝置主題衝突

## 生命週期與維護
- [x] 整合 lifespan 管理 MQTT 連線
- [x] 新增 /shutdown API 安全關閉伺服器
