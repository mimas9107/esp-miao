# 2026-03-04 伺服器優化項目排程 (TODO.md) - MISSION ACCOMPLISHED

## [Phase 1] 效能與穩定性 (100%)
- [x] 1. 關閉 Uvicorn Reload 並限制監控目錄。
- [x] 2. 實作單推論佇列 (max_workers=1)。
- [x] 3. 修復 aplay 殭屍進程。

## [Phase 2] myxiaomi HTTP 整合 (100%)
- [x] 1. 擴充 Device 模型支援 `api_url`。
- [x] 2. 實作通用派發器 `dispatch_command`。
- [x] 3. 註冊 `vacuum` 虛擬設備並配置別名。

## [Phase 3] 韌性強化 (100%)
- [x] 1. 將 API 超時增加至 10s (應對掃地機 UDP 延遲)。
- [x] 2. 擴充別名包含「少地」、「少弟」等 ASR 誤差詞。
- [x] 3. 實作掃地機「預設啟動」邏輯。

## [Final Test]
- [x] 1. 驗證「開燈/關燈」 (MQTT Path) -> Success.
- [x] 2. 驗證「小貓/機器人回去」 (HTTP Path) -> Success.
