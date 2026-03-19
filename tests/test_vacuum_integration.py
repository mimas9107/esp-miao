import json
import paho.mqtt.client as mqtt
import time
import os
import sys

# 將 src 加入路徑以便匯入
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from esp_miao.config import MQTT_BROKER, MQTT_AUTH_USER, MQTT_AUTH_PASSWORD, MQTT_DISCOVERY_TOPIC

DISCOVERY_TOPIC = MQTT_DISCOVERY_TOPIC
STATUS_TOPIC = "home/vacuum_01/status"
VACUUM_CONTROL_TOPIC = "home/vacuum/command"

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print(f"Connected to Broker at {MQTT_BROKER}")
        
        # 1. 發布 Online 狀態 (Retained)
        client.publish(STATUS_TOPIC, json.dumps({"status": "online", "device_id": "vacuum_01"}), retain=True)
        
        # 2. 發布 Discovery 訊息 (Retained)
        discovery_payload = {
            "device_id": "vacuum_01",
            "type": "vacuum",
            "aliases": ["掃地機器人", "小貓", "吸塵器", "機器人", "掃地機", "掃地", "清掃", "少地"],
            "control_topic": VACUUM_CONTROL_TOPIC,
            "commands": {
                "on": "START_CLEANING",
                "off": "GO_HOME"
            }
        }
        client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
        print("Discovery and Online status published.")
        
        # 3. 訂閱控制指令
        client.subscribe(VACUUM_CONTROL_TOPIC)
        print(f"Subscribed to {VACUUM_CONTROL_TOPIC}")
    else:
        print(f"Connection failed with code {rc}")

def on_message(client, userdata, msg):
    print(f"Received command: {msg.payload.decode()} on topic {msg.topic}")

def run_mock_vacuum():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    # 設定帳號密碼
    if MQTT_AUTH_USER and MQTT_AUTH_PASSWORD:
        client.username_pw_set(MQTT_AUTH_USER, MQTT_AUTH_PASSWORD)
    
    # 【關鍵】設定 LWT (Last Will and Testament)
    # 只要這個連線斷掉，Broker 就會發布這個訊息
    lwt_payload = json.dumps({"status": "offline", "device_id": "vacuum_01"})
    client.will_set(STATUS_TOPIC, lwt_payload, qos=1, retain=True)
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"Connecting to {MQTT_BROKER}...")
    client.connect(MQTT_BROKER, 1883, 60)
    
    try:
        # 使用 loop_forever 保持連線，直到被 Ctrl+C 中斷
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nMock Vacuum stopped by user.")
        # 注意：在真實測試 LWT 時，如果正常 disconnect，Broker 不會發 LWT。
        # 為了模擬「異常斷線」，我們可以直接結束程式而不呼叫 disconnect()。
        # 或者在測試環境中，我們手動發一個 offline 再離開，確保伺服器狀態更新。
        print("Publishing offline status before exit...")
        client.publish(STATUS_TOPIC, lwt_payload, retain=True)
        client.loop_stop()

if __name__ == "__main__":
    run_mock_vacuum()
