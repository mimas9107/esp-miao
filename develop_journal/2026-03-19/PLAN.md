# 修補計畫：移除靜態裝置依賴與實現動態下線機制 (PLAN)

> 日期：2026-03-19  
> 目的：修正 esp-miao server 與 Discovery 設計哲學的矛盾，解決裝置離線後狀態未同步的問題。

## 1. 核心目標
- **去中心化配置**：移除 Server 端所有硬編碼的靜態裝置與別名資訊。
- **動態狀態同步**：實現基於 MQTT LWT (Last Will and Testament) 的裝置下線偵測機制。
- **統一通訊路徑**：移除過時的 HTTP 直接控制路徑，全面轉向 MQTT 派發。

## 2. 策略與步驟

### Phase A: Server 端架構清理 (Patches 1, 2, 5)
1. **移除靜態初始化**：在 `connection.py` 中將 `device_table` 初始化改為空，確保所有裝置資訊皆來自 Discovery。
2. **移除靜態別名**：刪除 `connection.py` 中的 `defaults` 別名字典。
3. **移除 HTTP 路徑**：在 `dispatch.py` 中刪除 HTTP 分支，僅保留 MQTT 派發邏輯。同步在 `models.py` 的 `Device` 模型中移除 `api_url` 欄位。

### Phase B: 動態下線機制實現 (Patches 3, 4)
1. **補齊刪除邏輯**：在 `DynamicDeviceTable` 類別中新增 `remove_device()` 方法，確保能從記憶體中清除下線裝置及其別名。
2. **監聽下線消息**：修改 MQTT handler，訂閱 `home/+/status` topic。當接收到 `status: offline` 的 JSON 消息時，觸發 `remove_device()`。

### Phase C: 終端裝置補齊 (Patch 6)
1. **ESP32 落地燈更新**：在 Arduino 程式碼中加入 LWT 設定、online 消息發布，並確保 Discovery 包含完整的 `action_keywords`。
2. **myxiaomi (Mock/Bridge) 更新**：(假設存在對應服務) 確保其 Python Bridge 具備 LWT 與 Discovery 能力。

## 3. 風險控管
- **部署順序**：Server 清理與裝置更新必須同時進行。若 Server 領先更新但裝置未發布 Discovery，系統將短暫失效。
- **MQTT Retain**：確認 LWT 訊息使用 `retain=True`，以確保 Server 重啟後能立即得知當前最新的離線狀態。

## 4. 驗證標準
- Server 啟動時 `device_table` 為空。
- 裝置上線後自動出現在 `device_table`。
- 裝置手動斷電/斷線後，Server 應在數秒內（依 Broker LWT 設定）將其移除。
- 所有控制指令均透過 MQTT 發送，不產生 HTTP 請求。
