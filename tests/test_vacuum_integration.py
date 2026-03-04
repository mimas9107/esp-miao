import json
import paho.mqtt.client as mqtt
import time

MQTT_BROKER = "127.0.0.1" # 在本機測試
DISCOVERY_TOPIC = "home/discovery"
VACUUM_CONTROL_TOPIC = "home/vacuum/command"

def simulate_discovery():
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883, 60)
    
    discovery_payload = {
        "device_id": "robot_s5",
        "type": "vacuum",
        "aliases": ["掃地機器人", "小貓", "吸塵器"],
        "control_topic": VACUUM_CONTROL_TOPIC,
        "commands": {
            "on": "START_CLEANING",
            "off": "GO_HOME"
        }
    }
    
    print(f"Publishing discovery to {DISCOVERY_TOPIC}...")
    client.publish(DISCOVERY_TOPIC, json.dumps(discovery_payload), retain=True)
    client.disconnect()

def listen_for_commands():
    def on_connect(client, userdata, flags, rc):
        print(f"Subscribed to {VACUUM_CONTROL_TOPIC}")
        client.subscribe(VACUUM_CONTROL_TOPIC)

    def on_message(client, userdata, msg):
        print(f"Received command: {msg.payload.decode()}")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
    return client

if __name__ == "__main__":
    # 模擬 myxiaomi 監聽控制指令
    listener = listen_for_commands()
    
    # 模擬 myxiaomi 註冊設備
    simulate_discovery()
    
    print("Waiting for commands from esp-miao (Send voice: 嘿喵喵，啟動掃地機器人)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.loop_stop()
        print("Test stopped.")
