import os
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# --- Load Environment Variables ---
load_dotenv()

# --- Global Executor for CPU-bound tasks ---
# 在 RPi4 上，建議限制 max_workers=1 以避免多個 ASR/LLM 任務併發導致系統崩潰
inference_executor = ThreadPoolExecutor(max_workers=1)

# --- Resource Configuration ---
LOAD_MODEL_ON_START = os.getenv("LOAD_MODEL_ON_START", "1") == "1"
DEBUG_AUDIO_SAVE = os.getenv("DEBUG_AUDIO_SAVE", "0") == "1"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# --- Path Configuration ---
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "audio"
LOCAL_SOUND_DIR = BASE_DIR / "playsound"

# --- WebSocket Configuration ---
TIMEOUT_SECONDS = 10.0

# --- MQTT Configuration ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.16")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/generic/command")
MQTT_DISCOVERY_TOPIC = "home/discovery"
MQTT_AUTH_USER = os.getenv("MQTT_AUTH_USER")
MQTT_AUTH_PASSWORD = os.getenv("MQTT_AUTH_PASSWORD")

# --- LLM Intent Parsing Keywords ---
ACTION_KEYWORDS = {
    "on": ["開", "打開", "開啟", "啟動", "掃地", "清掃", "開始", "turn on", "on", "open", "kaitan"],
    "off": ["關", "關閉", "關掉", "停止", "回充", "充電", "回去", "回家", "turn off", "off", "close", "kuan teng"],
}
