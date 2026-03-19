# esp-miao 架構修補計畫

> 文件版本：v1.0  
> 建立日期：2026-03-19  
> 性質：獨立修補計畫，基於 code review 發現的設計缺陷  
> 前置文件：esp-miao-upgrade-plan.md（v2.0）

---

## 問題根源

升級計畫（Phases 1-4）雖已完成，但 code review 發現 esp-miao server 端仍存在**與 Discovery 設計哲學根本矛盾**的舊有架構殘留，導致整個 Discovery 機制的價值大打折扣。

### 核心矛盾

> esp-miao server 本身不應該知道家裡有哪些裝置。  
> 這份知識應該分散在每個裝置自己身上，透過 Discovery 動態建立。

**現況違反此原則的具體問題：**

**① `connection.py` — 靜態裝置預設值**
```python
device_table = DynamicDeviceTable(devices=[
    Device(name="light",  type="relay",  gpio=26, control_topic="lamp/command"),
    Device(name="fan",    type="relay",  gpio=27, control_topic="home/fan/command"),
    Device(name="led",    type="led",    gpio=2,  control_topic="home/led/command"),
    Device(name="vacuum", type="vacuum", aliases=[...], api_url="http://192.168.1.16:8009/..."),
])
```
server 啟動時就預先填好裝置，Discovery 機制形同虛設。

**② `connection.py` — 靜態 alias 預設值（`_update_aliases()` 內）**
```python
defaults = {
    "light": ["燈", "電燈", "燈光", "lights", "light"],
    "fan":   ["風扇", "電風扇", "電扇", "fans", "fan", "風山"],
    "led":   ["led", "LED", "指示燈"],
}
```
alias 的來源應全部來自 Discovery payload，不該有任何一個寫在 server 端。

**③ `connection.py` — `DynamicDeviceTable` 缺少下線清除機制**
只有 `update_device()`，沒有 `remove_device()`，裝置下線後 entry 永遠殘留。

**④ `dispatch.py` — HTTP 直呼叫路徑仍存在**
Phase 4-3 清理未完成，vacuum 靜態 entry 的 `api_url` 讓 dispatch 繞過 MQTT 走 HTTP，myxiaomi 停止時靜默失敗。

**⑤ 裝置 name 不一致**
靜態 entry `name="vacuum"` 與 myxiaomi Discovery 的 `device_id="vacuum_01"` 並存於 `_devices` dict，aliases 部分重疊但指向不同 entry，行為不可預測。

**⑥ `retain=True` 造成幽靈裝置**
myxiaomi Discovery 以 `retain=True` 發布，停止後 broker 仍保留 payload，esp-miao 重啟時 `vacuum_01` 會重新出現——但服務已停止。缺乏 LWT 機制，esp-miao 無法感知裝置真實存活狀態。

---

## 修補範圍總覽

| # | 影響範圍 | 性質 |
|---|---|---|
| Patch 1 | `connection.py` 靜態裝置初始化 | 刪除 |
| Patch 2 | `connection.py` 靜態 alias 預設值 | 刪除 |
| Patch 3 | `connection.py` DynamicDeviceTable | 新增 `remove_device()` |
| Patch 4 | `connection.py` MQTT handler | 新增 offline 監聽與清除邏輯 |
| Patch 5 | `dispatch.py` HTTP 路徑 | 刪除 |
| Patch 6 | 所有受控裝置韌體／服務 | 補齊 Discovery + LWT |

---

## Patch 1：移除靜態裝置初始化

**影響範圍：** `src/esp_miao/connection.py`

- [ ] 靜態初始化改為空 table
  ```python
  # Before
  device_table = DynamicDeviceTable(devices=[
      Device(name="light", ...),
      Device(name="fan",   ...),
      Device(name="led",   ...),
      Device(name="vacuum",...),
  ])

  # After
  device_table = DynamicDeviceTable()
  ```

- [ ] 確認 `DynamicDeviceTable.__init__` 可無參數初始化（目前已支援 `devices=None`，確認即可）

---

## Patch 2：移除靜態 alias 預設值

**影響範圍：** `src/esp_miao/connection.py` → `_update_aliases()`

- [ ] 刪除 `_update_aliases()` 中的 hardcoded `defaults` dict，改為純動態

  ```python
  # After
  def _update_aliases(self):
      self._aliases = {}
      for dev in self._devices.values():
          if dev.aliases:
              for alias in dev.aliases:
                  self._aliases[alias.lower()] = dev.name
  ```

---

## Patch 3：補上 `remove_device()`

**影響範圍：** `src/esp_miao/connection.py` → `DynamicDeviceTable`

- [ ] 新增 `remove_device()` 方法
  ```python
  def remove_device(self, name: str):
      if name in self._devices:
          del self._devices[name]
          if name in self._action_keyword_map:
              del self._action_keyword_map[name]
          self._update_aliases()
          logger.info(f"Device removed: {name}")
      else:
          logger.warning(f"remove_device: '{name}' not found in table")
  ```

---

## Patch 4：新增裝置下線監聽機制

**影響範圍：** `src/esp_miao/connection.py` → MQTT handler

### 設計：LWT + status topic 監聽

每個裝置負責在連線時設定 LWT，斷線時 broker 自動發布 offline 訊息。
esp-miao 訂閱 `home/+/status`，收到 `offline` 時呼叫 `remove_device()`。

- [ ] **訂閱 status wildcard topic**
  ```python
  def on_connect(client, userdata, flags, rc, properties):
      if rc == 0:
          client.subscribe(MQTT_DISCOVERY_TOPIC)
          client.subscribe("home/+/status")   # 新增
  ```

- [ ] **新增 MQTT message handler**
  ```python
  def on_mqtt_message(client, userdata, msg):
      if msg.topic == MQTT_DISCOVERY_TOPIC:
          # 現有 Discovery 處理邏輯
          ...
      elif msg.topic.endswith("/status"):
          try:
              payload = json.loads(msg.payload.decode())
              if payload.get("status") == "offline":
                  device_id = payload.get("device_id")
                  if device_id:
                      device_table.remove_device(device_id)
          except Exception as e:
              logger.warning(f"Failed to parse status message: {e}")

  mqtt_client.on_message = on_mqtt_message
  ```

---

## Patch 5：移除 `dispatch.py` 的 HTTP 路徑

**影響範圍：** `src/esp_miao/dispatch.py`

- [ ] 刪除 `if device.api_url:` 整個 HTTP 分支
- [ ] 所有裝置統一走 MQTT publish
- [ ] 同步清理 `Device` model 中的 `api_url` 欄位（`models.py`）

  ```python
  # After：dispatch_command 只剩 MQTT 路徑
  async def dispatch_command(target, value, metrics_ctx=None):
      device = device_table.get_device(target)
      if not device:
          logger.warning(f"Attempted to control unregistered device: {target}")
          if metrics_ctx: metrics_ctx.set_error("unregistered_device")
          return

      topic = device.control_topic if device.control_topic else MQTT_TOPIC
      commands = device.commands if device.commands else {"on": "ON", "off": "OFF"}
      cmd_payload = commands.get(value.lower(), value.upper())

      try:
          result = mqtt_client.publish(topic, cmd_payload)
          if result.rc == 0:
              logger.info(f"MQTT Publish: [{topic}] -> {cmd_payload} (for {target})")
              if metrics_ctx: metrics_ctx.set_flag("dispatch_success", True)
          else:
              logger.error(f"MQTT publish failed for {target} (rc={result.rc})")
              if metrics_ctx: metrics_ctx.set_error(f"mqtt_error_rc{result.rc}")
      except Exception as e:
          logger.error(f"MQTT Publish Error for {target}: {e}")
          if metrics_ctx: metrics_ctx.set_error("mqtt_exception")
  ```

---

## Patch 6：所有裝置補齊 Discovery + LWT

**目標：每個受控裝置都要做到三件事，Patch 4 的機制才能真正運作。**

1. 連線前設定 LWT → 斷線時 broker 自動發布 offline
2. 連線成功後發布 online 狀態
3. 連線成功後發布 Discovery（含完整 `aliases`、`action_keywords`、`commands`、`control_topic`）

### 6-A：ESP32 落地燈（`mqtt_for_esp32/`）

- [ ] 連線時設定 LWT
  ```cpp
  mqttClient.setWill(
      "home/light_01/status",
      "{\"status\":\"offline\",\"device_id\":\"light_01\"}",
      true,  // retain
      1      // QoS
  );
  ```

- [ ] 連線成功後發布 online + Discovery
  ```cpp
  mqttClient.publish("home/light_01/status",
      "{\"status\":\"online\",\"device_id\":\"light_01\"}", true);
  sendDiscoveryMessage();
  ```

### 6-B：myxiaomi / vacuumd（`vacuumd/mqtt_bridge.py`）

- [ ] `connect()` 中加入 LWT 設定
  ```python
  client.will_set(
      STATUS_TOPIC,  # "home/vacuum_01/status"
      json.dumps({"status": "offline", "device_id": "vacuum_01"}, ensure_ascii=False),
      qos=1,
      retain=True
  )
  ```

- [ ] `_on_connect` 中發布 online 狀態（`publish_discovery()` 已在 Phase 4-2 實作）
  ```python
  def _on_connect(self, client, _userdata, _flags, rc):
      if rc != 0:
          ...
          return
      with self._lock:
          self._connected = True
          client.subscribe(CONTROL_TOPIC)
      self._publish(STATUS_TOPIC,
          {"status": "online", "device_id": "vacuum_01"}, retain=True)
      self.publish_discovery()
  ```

### 6-C：未來新裝置設計規範

新增任何受 esp-miao 控制的裝置，**必須實作以下三項**，否則不得接入系統：

| 項目 | Topic | Payload 格式 | retain |
|---|---|---|---|
| LWT（斷線時自動發布）| `home/{device_id}/status` | `{"status":"offline","device_id":"..."}` | true |
| 上線通知 | `home/{device_id}/status` | `{"status":"online","device_id":"..."}` | true |
| Discovery | `home/discovery` | 完整 metadata（見下方） | true |

Discovery payload 必要欄位：
```json
{
  "device_id":       "xxx_01",
  "device_type":     "relay | vacuum | led | ...",
  "aliases":         ["裝置別名", "..."],
  "control_topic":   "home/xxx_01/cmd",
  "commands":        {"on": "ON", "off": "OFF"},
  "action_keywords": {"on": ["開", "..."], "off": ["關", "..."]}
}
```

---

## 執行順序與部署注意

```
Patch 1 + Patch 2   ←─ 必須同步完成（server 清空靜態資料）
      ↓
Patch 3 + Patch 4   （補下線清除機制）
      ↓
Patch 5             （移除 HTTP dispatch）
      ↓
Patch 6-A  Patch 6-B  ←─ 可平行，但需與 Patch 1+2 同一次部署
      ↓
整合驗證
```

> ⚠️ **部署空窗期警告**  
> Patch 1+2（清空 server 靜態資料）與 Patch 6（裝置補 Discovery）必須**同一次部署**。  
> 若只做 Patch 1+2 而裝置尚未補 Discovery，server 啟動後 device table 為空，所有語音指令失效。

---

## 整合驗證清單

- [ ] esp-miao server 冷啟動後 device table 為空
- [ ] 落地燈上線 → `light_01` 進 table，alias「燈」可觸發
- [ ] myxiaomi 上線 → `vacuum_01` 進 table，alias「小貓」可觸發
- [ ] 說「開燈」→ MQTT publish 到 `home/light_01/cmd`（不走 HTTP）
- [ ] 說「掃地」→ MQTT publish 到 `home/vacuum_01/cmd`（不走 HTTP）
- [ ] myxiaomi 停止 → broker 發 LWT → `vacuum_01` 從 table 移除
- [ ] myxiaomi 停止後說「掃地」→ intent 解析 unknown，不產生靜默失敗
- [ ] myxiaomi 重啟 → `vacuum_01` 重新進 table，恢復正常
- [ ] esp-miao 重啟（myxiaomi 停止中）→ broker retained payload 不應讓 `vacuum_01` 重新出現
  > 注意：此項需確認 myxiaomi 停止時 LWT 有正確覆蓋掉 retained online/discovery payload

---

## 附錄：修補前後 dispatch 流向對比

**修補前（現況）**
```
說「掃地」
  → intent: target=vacuum（靜態 entry）或 vacuum_01（Discovery entry），兩者並存
  → dispatch: device.api_url 存在 → HTTP POST myxiaomi
  → myxiaomi 停止 → Connection refused → 靜默失敗，使用者無反饋
```

**修補後（目標）**
```
說「掃地」
  → myxiaomi 運行中：intent: target=vacuum_01（唯一 entry）→ MQTT publish → 正常執行
  → myxiaomi 停止中：LWT 已觸發 remove_device → intent 解析 unknown → 不派發，不靜默失敗
```
