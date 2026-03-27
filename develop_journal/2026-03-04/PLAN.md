# 2026-03-04 伺服器優化與跨專案對接計畫 (PLAN.md) - Final Success

## 1. 效能優化 (Completed)
- **待機降載**: 關閉 Uvicorn Reload，RPi4 待機 CPU 降至 10%。
- **資源隔離**: 實作 ThreadPoolExecutor(max_workers=1)，防止併發崩潰。
- **殭屍進程修復**: 使用 asyncio 子進程管理徹底消滅 <defunct> aplay。

## 2. 跨專案整合：myxiaomi 直連 (Completed)
- **策略轉向**: 放棄較複雜的 MQTT Discovery 雙向修改，改用「HTTP API 直連」方案。
- **實施**: `esp-miao` 作為 Client 調用 `myxiaomi:8009` 的 REST 接口。
- **效益**: 達成 myxiaomi 端「零代碼改動」的完美整合。

## 3. 韌性與容錯優化 (Hotfixed)
- **超時處理**: 針對硬體反應慢的特性，將 HTTP Timeout 放寬至 10s。
- **ASR 容錯**: 擴充別名清單，納入「少地」等同音誤差詞，並實作掃地機「預設啟動」語意。

## 4. 最終結論
系統已具備工業級穩定度與靈活的跨專案擴充能力。
