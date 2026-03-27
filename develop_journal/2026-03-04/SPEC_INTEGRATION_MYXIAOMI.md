# 跨專案語音控制對接規格書 (v1.1)
**對象專案**: `myxiaomi` (亦稱 `vacuumd`)

## 1. 概觀
本文件定義 `myxiaomi` 服務如何透過 MQTT 協議自動向 `esp-miao` 語音中樞註冊掃地機器人設備，並接收語音指令進行控制。

## 2. MQTT 連線資訊
*   **Broker**: `192.168.1.16` (RPi4 預設)
*   **Port**: `1883`
*   **Discovery Topic**: `home/discovery` (註冊用)
*   **Control Topic**: `home/vacuum/command` (控制用，可自定義)

## 3. 設備註冊 (MQTT Discovery)
`myxiaomi` 服務啟動時，應向 `home/discovery` 發送一個 **Retained** 的 JSON 訊息。

### 推薦 Payload (範例):
```json
{
  "device_id": "robot_s5",
  "type": "vacuum",
  "aliases": ["掃地機器人", "掃地機", "小貓", "吸塵器"],
  "control_topic": "home/vacuum/command",
  "commands": {
    "on": "START",
    "off": "HOME"
  }
}
```

### 欄位定義:
- `device_id`: 設備唯一識別碼（建議使用 `robot_s5`）。
- `type`: 設備類型，填寫 `vacuum`。
- `aliases`: **關鍵字地圖**。當使用者說出這些詞時，`esp-miao` 會將意圖導向此設備。
- `control_topic`: `esp-miao` 發送控制指令的頻道。
- `commands`: 動作映射。
    - `"on"`: 當語音辨識為「啟動/開始」時發送的字串。
    - `"off"`: 當語音辨識為「停止/回充」時發送的字串。

## 4. 控制指令接收處理
`myxiaomi` 應訂閱 `control_topic` (如 `home/vacuum/command`)。

### 邏輯對照表:
| 接收到的 Payload | 應呼叫之 `VacuumController` 方法 |
| :--- | :--- |
| `START` | `controller.start()` |
| `HOME` | `controller.home()` |

## 5. 實作建議 (myxiaomi 團隊)
1.  在 `vacuumd/controller/manager.py` 或獨立的 `mqtt_client.py` 中實作連線。
2.  啟動時立即發佈 Discovery 訊息。
3.  接收到指令後，直接調用已有的 `VacuumController` 實例。
4.  建議使用 `paho-mqtt` 套件。

---
**esp-miao 端對應**:
語音中樞在收到 Discovery 訊息後，會自動更新內部的設備表。下次使用者說「嘿喵喵，啟動掃地機器人」時，中樞會解析出 `target="robot_s5", value="on"`，並向 `home/vacuum/command` 發送 `START`。
