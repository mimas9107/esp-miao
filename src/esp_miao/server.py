"""ESP-MIAO FastAPI WebSocket Server

Handles ESP32 voice agent communication and LLM intent parsing.
"""

import asyncio
import base64
import json
import logging
import time
import io
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
import ollama
from faster_whisper import WhisperModel

from .models import (
    Action,
    ActionPayload,
    ActionValidator,
    AudioRequest,
    AudioStreamStart,
    AudioStreamChunk,
    CommandRequest,
    DeviceTable,
    Device,
    FallbackRequest,
    Play,
    PlayPayload,
    TimeSync,
    TimeSyncPayload,
    ALLOWED_ACTIONS,
)

import uvicorn
import paho.mqtt.client as mqtt
import os
import httpx
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from .metrics import init_metrics, shutdown_metrics, metrics_logger, aggregator, MetricsContext

# --- Load Environment Variables ---
load_dotenv()

# --- Global Executor for CPU-bound tasks ---
# 在 RPi4 上，建議限制 max_workers=1 以避免多個 ASR/LLM 任務併發導致系統崩潰
inference_executor = ThreadPoolExecutor(max_workers=1)

# --- Resource Configuration ---
# 預設為 1 (啟動即載入)，確保第一聲指令即時響應。在 RPi4 記憶體極度不足時可設為 0 改用 Lazy Load。
LOAD_MODEL_ON_START = os.getenv("LOAD_MODEL_ON_START", "1") == "1"
DEBUG_AUDIO_SAVE = os.getenv("DEBUG_AUDIO_SAVE", "0") == "1" # 預設關閉以節省 IO

# --- ASR Pipeline (Faster-Whisper) ---
whisper_model: Optional[WhisperModel] = None

def get_whisper_model() -> WhisperModel:
    """單例模式獲取 Whisper 模型，支援延遲加載。"""
    global whisper_model
    if whisper_model is None:
        logger.info("Initializing Whisper model (base, cpu)...")
        start_time = time.perf_counter()
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        elapsed = time.perf_counter() - start_time
        logger.info(f"Whisper model loaded in {elapsed:.2f} seconds.")
    return whisper_model

# --- Logging setup ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("esp-miao")


# --- Configuration ---
AUDIO_DIR = Path(__file__).parent / "audio"
LOCAL_SOUND_DIR = Path(__file__).parent / "playsound"
TIMEOUT_SECONDS = 10.0  # WebSocket response timeout

async def play_local_sound(filename: str):
    """Play a sound file locally on the server using non-blocking subprocess."""
    if not filename:
        return

    sound_path = LOCAL_SOUND_DIR / filename
    if not sound_path.exists():
        logger.warning(f"Local sound file not found: {sound_path}")
        return

    try:
        logger.info(f"Playing local sound: {filename}")
        # 使用 asyncio 的子進程管理，能自動處理收割 (reap) 以防止殭屍進程 <defunct>
        proc = await asyncio.create_subprocess_exec(
            "aplay", str(sound_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        # 在背景等待進程結束，不阻塞當前的 WebSocket 任務
        asyncio.create_task(proc.wait())
    except Exception as e:
        logger.error(f"Failed to play local sound {filename}: {e}")


def get_action_sound(target: str, value: str) -> str:
    """Determine the sound file to play based on the action target and value."""
    if target == "light":
        return "lightopen.wav" if value == "on" else "lightclose.wav"
    
    # Default success sound for other devices
    return "success.wav"

MQTT_BROKER = os.getenv("MQTT_BROKER", "192.168.1.16")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "home/generic/command") # 改為更通用的主題
MQTT_DISCOVERY_TOPIC = "home/discovery"
MQTT_AUTH_USER = os.getenv("MQTT_AUTH_USER")
MQTT_AUTH_PASSWORD = os.getenv("MQTT_AUTH_PASSWORD")

# --- Device & Discovery Support ---
class DynamicDeviceTable:
    def __init__(self, devices: list[Device] = None):
        self._devices: dict[str, Device] = {d.name: d for d in (devices or [])}
        self._aliases: dict[str, str] = {} # alias -> device_name
        self._update_aliases()

    def _update_aliases(self):
        """Rebuild alias map from current devices."""
        self._aliases = {}
        # Hardcoded defaults for backward compatibility
        defaults = {
            "light": ["燈", "電燈", "燈光", "lights", "light"],
            "fan": ["風扇", "電風扇", "電扇", "fans", "fan", "風山"],
            "led": ["led", "LED", "指示燈"],
        }
        for name, aliases in defaults.items():
            for alias in aliases:
                self._aliases[alias] = name
        
        # Add dynamic aliases from discovered devices
        for dev in self._devices.values():
            if dev.aliases:
                for alias in dev.aliases:
                    self._aliases[alias.lower()] = dev.name

    def update_device(self, dev_info: dict):
        """Register or update a device from MQTT discovery."""
        # 同時支援 'name' 或 'device_id' 以利外部對接
        name = dev_info.get("name") or dev_info.get("device_id")
        if not name:
            logger.warning("Received discovery payload without name/device_id")
            return
        
        # 同時支援 'type' 或 'device_type'
        dev_type = dev_info.get("type") or dev_info.get("device_type", "unknown")
        
        # Create Device object (Mapping discovery fields to Device model)
        new_dev = Device(
            name=name,
            type=dev_type,
            gpio=dev_info.get("gpio"),
            aliases=dev_info.get("aliases", []),
            control_topic=dev_info.get("control_topic", MQTT_TOPIC),
            commands=dev_info.get("commands", {"on": "ON", "off": "OFF"})
        )
        self._devices[name] = new_dev
        self._update_aliases()
        logger.info(f"Device registered/updated: {name} ({new_dev.type})")

    @property
    def devices(self) -> list[Device]:
        return list(self._devices.values())

    @property
    def alias_map(self) -> dict[str, str]:
        return self._aliases

    def get_device(self, name: str) -> Optional[Device]:
        return self._devices.get(name)

# Initialize with static defaults
# 注意：為了向後相容 Board B 範例，我們將靜態 light 的 Topic 設為 "lamp/command"
# 其餘設備改用專屬 Topic 避免衝突
device_table = DynamicDeviceTable(devices=[
    Device(name="light", type="relay", gpio=26, control_topic="lamp/command"),
    Device(name="fan", type="relay", gpio=27, control_topic="home/fan/command"),
    Device(name="led", type="led", gpio=2, control_topic="home/led/command"),
    # 新增掃地機器人 (直連 myxiaomi API)
    Device(
        name="vacuum", 
        type="vacuum", 
        aliases=["掃地機器人", "小貓", "吸塵器", "機器人", "掃地機", "掃地", "清掃", "少地"],
        api_url="http://192.168.1.16:8009/v1/control/execute",
        commands={"on": "start", "off": "home"}
    ),
])

# --- MQTT Setup ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

if MQTT_AUTH_USER and MQTT_AUTH_PASSWORD:
    mqtt_client.username_pw_set(MQTT_AUTH_USER, MQTT_AUTH_PASSWORD)

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_DISCOVERY_TOPIC)
        logger.info(f"Subscribed to discovery topic: {MQTT_DISCOVERY_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

async def dispatch_command(target: str, value: str, metrics_ctx: Optional[MetricsContext] = None):
    """通用指令派發器，支援 MQTT 與 HTTP API。"""
    device = device_table.get_device(target)
    if not device:
        logger.warning(f"Attempted to control unregistered device: {target}")
        if metrics_ctx: metrics_ctx.set_error("unregistered_device")
        return

    # 決定發送方式：API 優先，MQTT 為輔
    if device.api_url:
        # HTTP API 模式 (針對 myxiaomi 等已有服務的專案)
        if metrics_ctx: metrics_ctx.mark_stage("dispatch_type", "http_api")
        
        cmd_payload = device.commands.get(value.lower(), value)
        logger.info(f"HTTP API Call: [{device.api_url}] -> cmd={cmd_payload} (for {target})")
        
        try:
            # 針對 myxiaomi (vacuumd) 的 CommandRequest 格式
            # device_id 在 myxiaomi 端固定為 robot_s5 (除非 Discovery 修改)
            payload = {
                "device_id": "robot_s5", 
                "command": cmd_payload
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(device.api_url, json=payload)
                if response.status_code == 200:
                    logger.info(f"HTTP Success: {response.json()}")
                    if metrics_ctx: metrics_ctx.set_flag("dispatch_success", True)
                else:
                    logger.error(f"HTTP Error {response.status_code}: {response.text}")
                    if metrics_ctx: metrics_ctx.set_error(f"http_error_{response.status_code}")
        except Exception as e:
            logger.error(f"HTTP Request failed for {target}: {e}")
            if metrics_ctx: metrics_ctx.set_error("http_exception")
    
    else:
        # MQTT 模式 (針對嵌入式裸機)
        if metrics_ctx: metrics_ctx.mark_stage("dispatch_type", "mqtt")
        
        topic = device.control_topic if device.control_topic else MQTT_TOPIC
        commands = device.commands if device.commands else {"on": "ON", "off": "OFF"}
        cmd_payload = commands.get(value.lower(), value.upper())

        try:
            result = mqtt_client.publish(topic, cmd_payload)
            if result.rc == 0:
                logger.info(f"MQTT Publish: [{topic}] -> {cmd_payload} (for {target})")
                if metrics_ctx: metrics_ctx.set_flag("dispatch_success", True)
            else:
                logger.error(f"Failed to publish MQTT command for {target} (rc={result.rc})")
                if metrics_ctx: metrics_ctx.set_error(f"mqtt_error_rc{result.rc}")
        except Exception as e:
            logger.error(f"MQTT Publish Error for {target}: {e}")
            if metrics_ctx: metrics_ctx.set_error("mqtt_exception")

# --- Action Validator (Safety) ---
action_validator = ActionValidator(device_table)


# --- Local Command Mapping ---
LOCAL_COMMANDS = {
    0: ("LIGHT_ON", "light", "on"),
    1: ("LIGHT_OFF", "light", "off"),
    2: ("FAN_ON", "fan", "on"),
    3: ("FAN_OFF", "fan", "off"),
}


# --- Connection Manager ---
class ConnectionManager:
    """Manage active WebSocket connections with timeout support."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.pending_responses: dict[str, asyncio.Future] = {}
        self.audio_buffers: dict[str, bytearray] = {}  # Store chunked audio per device
        self.session_confidence: dict[str, float] = {}  # Store confidence per session
        self.transfer_modes: dict[str, str] = {}  # "base64" or "binary"
        self.expected_bytes: dict[str, int] = {}  # Expected total bytes for binary mode

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        self.audio_buffers[device_id] = bytearray()
        logger.info(f"Device connected: {device_id}")

    def disconnect(self, device_id: str):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            logger.info(f"Device disconnected: {device_id}")
        if device_id in self.audio_buffers:
            del self.audio_buffers[device_id]
        if device_id in self.session_confidence:
            del self.session_confidence[device_id]
        if device_id in self.transfer_modes:
            del self.transfer_modes[device_id]
        if device_id in self.expected_bytes:
            del self.expected_bytes[device_id]
        # Cancel any pending futures
        if device_id in self.pending_responses:
            self.pending_responses[device_id].cancel()
            del self.pending_responses[device_id]

    def clear_audio_buffer(self, device_id: str, confidence: Optional[float] = None, 
                           transfer_mode: str = "base64", total_samples: int = 0):
        """Clear the audio buffer for a device and set session context."""
        if device_id in self.audio_buffers:
            self.audio_buffers[device_id] = bytearray()
        
        if confidence is not None:
            self.session_confidence[device_id] = confidence
        else:
            self.session_confidence.pop(device_id, None)

        self.transfer_modes[device_id] = transfer_mode
        self.expected_bytes[device_id] = total_samples * 2  # 16-bit = 2 bytes per sample
            
        logger.debug(f"Cleared audio buffer for {device_id}, mode: {transfer_mode}, expected: {self.expected_bytes[device_id]}")

    def append_audio_data(self, device_id: str, data: bytes):
        """Append data to the audio buffer for a device."""
        if device_id not in self.audio_buffers:
            self.audio_buffers[device_id] = bytearray()
        self.audio_buffers[device_id].extend(data)

    def get_audio_data(self, device_id: str) -> bytes:
        """Get the full audio data from the buffer."""
        return bytes(self.audio_buffers.get(device_id, b""))

    async def send_to_device(self, device_id: str, message: dict) -> bool:
        """Send message to device. Returns True if successful."""
        if device_id in self.active_connections:
            try:
                await self.active_connections[device_id].send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Failed to send to {device_id}: {e}")
                return False
        return False

    async def send_with_timeout(
        self, device_id: str, message: dict, timeout: float = TIMEOUT_SECONDS
    ) -> Optional[dict]:
        """Send message and wait for response with timeout."""
        if not await self.send_to_device(device_id, message):
            return None

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending_responses[device_id] = future

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response from {device_id}")
            return None
        finally:
            if device_id in self.pending_responses:
                del self.pending_responses[device_id]

    def resolve_pending(self, device_id: str, response: dict):
        """Resolve pending future with response."""
        if device_id in self.pending_responses:
            if not self.pending_responses[device_id].done():
                self.pending_responses[device_id].set_result(response)

    def get_connection(self, device_id: str) -> Optional[WebSocket]:
        return self.active_connections.get(device_id)

    def list_connected_devices(self) -> list[str]:
        return list(self.active_connections.keys())


manager = ConnectionManager()


# --- ASR Pipeline (Faster-Whisper) ---
whisper_model: Optional[WhisperModel] = None


async def transcribe_audio(
    audio_base64: str, audio_format: str = "pcm_16k_16bit"
) -> str:
    """
    Transcribe audio to text using faster-whisper.
    """
    try:
        model = get_whisper_model()
        
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(audio_base64)
        
        # 使用 io.BytesIO 在記憶體中建立 WAV 格式資料，避免磁碟 I/O
        from struct import pack
        wav_buf = io.BytesIO()
        sample_rate = 16000
        bits_per_sample = 16
        channels = 1
        data_size = len(audio_bytes)
        
        wav_buf.write(b"RIFF")
        wav_buf.write(pack("<I", 36 + data_size))
        wav_buf.write(b"WAVE")
        wav_buf.write(b"fmt ")
        wav_buf.write(pack("<I", 16))
        wav_buf.write(pack("<H", 1))
        wav_buf.write(pack("<H", channels))
        wav_buf.write(pack("<I", sample_rate))
        wav_buf.write(pack("<I", sample_rate * channels * (bits_per_sample // 8)))
        wav_buf.write(pack("<H", channels * (bits_per_sample // 8)))
        wav_buf.write(pack("<H", bits_per_sample))
        wav_buf.write(b"data")
        wav_buf.write(pack("<I", data_size))
        wav_buf.write(audio_bytes)
        wav_buf.seek(0)

        # 定義阻塞推論的同步函式
        def run_transcription():
            segments, info = model.transcribe(
                wav_buf, 
                beam_size=3, # 優化：縮小 beam_size 換取速度
                language="zh",
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )
            
            text_segments = []
            for segment in segments:
                if segment.no_speech_prob < 0.7:
                    clean_text = segment.text.strip()
                    # 幻聽攔截邏輯保持不變
                    if len(clean_text) >= 4:
                        half = len(clean_text) // 2
                        if clean_text[:half] == clean_text[half:]:
                            continue
                        if all(c == clean_text[0] for c in clean_text[:4]):
                            continue
                    text_segments.append(clean_text)
            return "".join(text_segments).strip(), info

        # 使用全域受限的 executor 執行阻塞式的 Whisper 推論，防止 CPU 飽和
        loop = asyncio.get_event_loop()
        text, info = await loop.run_in_executor(inference_executor, run_transcription)
        
        if text:
            logger.info(f"ASR (Whisper) [{info.language}]: {text}")
        return text

    except Exception as e:
        logger.error(f"ASR error: {e}")
        return ""


# --- LLM Intent Parsing ---

# 動作關鍵字 (全局共通)
ACTION_KEYWORDS: dict[str, list[str]] = {
    "on": ["開", "打開", "開啟", "啟動", "掃地", "清掃", "開始", "turn on", "on", "open", "kaitan"],
    "off": ["關", "關閉", "關掉", "停止", "回充", "充電", "回去", "回家", "turn off", "off", "close", "kuan teng"],
}


def extract_intent_from_text(text: str) -> dict:
    """
    使用從 DeviceRegistry 獲獲取的動態別名地圖進行匹配。
    """
    text_lower = text.replace(" ", "").lower()

    # 找出目標裝置 (動態查詢 alias_map)
    target = None
    for alias, device_name in device_table.alias_map.items():
        if alias in text_lower:
            target = device_name
            break

    # 找出動作
    value = None
    for action_value, keywords in ACTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                value = action_value
                break
        if value:
            break

    if target and value:
        return {"action": "relay_set", "target": target, "value": value}
    
    # 針對掃地機器人的特殊處理：如果只說了名字（例如：小貓），預設為啟動
    if target:
        device = device_table.get_device(target)
        if device and device.type == "vacuum":
            logger.info(f"Defaulting to 'on' for vacuum target: {target}")
            return {"action": "relay_set", "target": target, "value": "on"}
        return {"action": "unknown", "target": target, "value": ""}

    return {"action": "unknown", "target": "", "value": ""}


def parse_intent_with_llm(text: str, metrics_ctx: Optional[MetricsContext] = None) -> dict:
    """Use Ollama LLM to parse natural language intent with dynamic device list."""
    current_devices = [d.name for d in device_table.devices]

    # 先用關鍵字匹配提取意圖（作為驗證基準）
    keyword_intent = extract_intent_from_text(text)
    logger.debug(f"Keyword extraction: {text} -> {keyword_intent}")
    
    # 記錄關鍵字命中
    if metrics_ctx:
        metrics_ctx.set_flag("keyword_action_found", keyword_intent["action"] != "unknown")
        metrics_ctx.set_flag("keyword_target_found", keyword_intent["target"] != "")
    
    # --- 優先攔截邏輯 (Priority Logic) ---
    # 如果關鍵字已經能明確識別出目標與動作，直接返回，跳過 LLM 以降低延遲
    if keyword_intent["action"] != "unknown" and keyword_intent["target"] in current_devices:
        logger.info(f"Priority Logic: Keyword match successful for '{text}', skipping LLM.")
        if metrics_ctx: metrics_ctx.set_flag("llm_called", False)
        return keyword_intent

    # 如果內容完全沒提到裝置名稱且關鍵字解析失敗，不送 LLM，直接回傳 unknown
    if keyword_intent["target"] == "" and keyword_intent["action"] == "unknown":
        logger.info(f"Pre-filter: No devices found in '{text}', skipping LLM.")
        if metrics_ctx: metrics_ctx.set_flag("llm_called", False)
        return keyword_intent

    # 方案 B: 動態 LLM Prompt
    if metrics_ctx: metrics_ctx.set_flag("llm_called", True)
    
    prompt = f"""Task: Convert voice command to JSON.
Available devices: {current_devices}

Examples:
- Command: "幫我開燈" -> {{"action": "relay_set", "target": "light", "value": "on"}}
- Command: "關掉風扇" -> {{"action": "relay_set", "target": "fan", "value": "off"}}

Command: "{text}"
Response in ONE LINE JSON format ONLY:
"""

    try:
        t_llm = time.time()
        response = ollama.generate(model="qwen2.5:0.5b", prompt=prompt)
        if metrics_ctx: metrics_ctx.record_latency("llm_inference_latency", round(time.time() - t_llm, 3))
        
        result_text = response["response"]

        # Extract JSON from response
        import re
        json_match = re.search(r"\{[^}]+\}", result_text)
        if json_match:
            result_text = json_match.group()

        result = json.loads(result_text.strip())
        logger.info(f"LLM parsed: {text} -> {result}")

        # 驗證邏輯：如果 LLM 回報無效裝置，使用關鍵字結果
        if result.get("target") not in current_devices or result.get("value") not in ["on", "off"]:
            logger.warning(f"LLM output invalid device or value, falling back to keywords")
            return keyword_intent
            
        # 交叉驗證：以關鍵字匹配結果為準（如果存在）
        if keyword_intent["action"] != "unknown":
            if result.get("target") != keyword_intent["target"] or result.get("value") != keyword_intent["value"]:
                logger.warning(f"LLM disagreed with keywords, prioritizing keywords: {keyword_intent}")
                return keyword_intent

        if metrics_ctx: metrics_ctx.set_flag("llm_success", True)
        return result

    except Exception as e:
        logger.error(f"LLM parse error: {e}, using keyword result")
        return keyword_intent


# --- Message Handlers ---
async def handle_command_request(device_id: str, data: dict) -> dict:
    """Handle local command from esp-sr."""
    try:
        msg = CommandRequest(**data)
        cmd_id = msg.payload.cmd_id

        if cmd_id in LOCAL_COMMANDS:
            cmd_name, target, value = LOCAL_COMMANDS[cmd_id]
            logger.info(f"Local command: {cmd_name} -> {target}={value}")

            # Safety: Validate action
            is_valid, error = action_validator.validate("relay_set", target, value)
            if not is_valid:
                logger.warning(f"Action validation failed: {error}")
                await play_local_sound("error.wav")
                return Play(
                    device_id=device_id,
                    timestamp=int(time.time() * 1000),
                    payload=PlayPayload(audio="error.wav"),
                ).model_dump()

            await play_local_sound(get_action_sound(target, value))
            await dispatch_command(target, value)
            return Action(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=ActionPayload(
                    action="relay_set",
                    target=target,
                    value=value,
                    sound=get_action_sound(target, value),
                ),
            ).model_dump()
        else:
            logger.warning(f"Unknown command ID: {cmd_id}")
            await play_local_sound("error.wav")
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="error.wav"),
            ).model_dump()

    except Exception as e:
        logger.error(f"Command request error: {e}")
        return Play(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=PlayPayload(audio="error.wav"),
        ).model_dump()


async def handle_fallback_request(device_id: str, data: dict) -> dict:
    """Handle fallback request with ASR + LLM."""
    try:
        msg = FallbackRequest(**data)

        # Get text from payload or transcribe audio
        text = msg.payload.text
        if not text and msg.payload.audio_base64:
            text = await transcribe_audio(
                msg.payload.audio_base64, msg.payload.audio_format or "pcm_16k_16bit"
            )

        if not text:
            logger.warning("No text or audio in fallback request")
            await play_local_sound("not_understood.wav")
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()

        logger.info(f"Fallback request: {text}")
        intent = parse_intent_with_llm(text)

        if intent.get("action") == "unknown":
            await play_local_sound("not_understood.wav")
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()

        # Safety: Validate action
        action = intent.get("action", "relay_set")
        target = intent.get("target", "")
        value = intent.get("value", "")

        is_valid, error = action_validator.validate(action, target, value)
        if not is_valid:
            logger.warning(f"LLM action validation failed: {error}")
            # Fail-safe: return error instead of executing unsafe action
            await play_local_sound("error.wav")
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="error.wav"),
            ).model_dump()

        await play_local_sound(get_action_sound(target, value))
        await dispatch_command(target, value)
        return Action(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=ActionPayload(
                action=action,
                target=target,
                value=value,
                sound=get_action_sound(target, value),
            ),
        ).model_dump()

    except Exception as e:
        logger.error(f"Fallback request error: {e}")
        return Play(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=PlayPayload(audio="error.wav"),
        ).model_dump()


async def handle_audio_request(device_id: str, data: dict) -> dict:
    """Handle standard audio_request from ESP32."""
    try:
        msg = AudioRequest(**data)
        audio_base64 = msg.payload.audio_base64
        audio_format = msg.payload.audio_format or "pcm_16k_16bit"
        confidence = msg.payload.confidence
        return await process_complete_audio(device_id, audio_base64, audio_format, confidence)
    except Exception as e:
        logger.error(f"Audio request error: {e}")
        return Play(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=PlayPayload(audio="error.wav"),
        ).model_dump()


async def process_complete_audio(
    device_id: str, audio_base64: str, audio_format: str, confidence: Optional[float] = None
) -> dict:
    """Core audio processing pipeline (ASR + LLM)."""
    # 1. Start Metrics Context
    request_id = f"{device_id}_{int(time.time()*1000)}"
    metrics_ctx = MetricsContext(request_id, device_id)
    
    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(audio_base64)
        
        # If confidence not provided, try to get from session
        if confidence is None:
            confidence = manager.session_confidence.get(device_id)

        logger.info(f" Audio processing: {len(audio_bytes)} bytes (confidence: {confidence})")

        # --- 背景儲存邏輯 (Background Storage) ---
        def save_audio_file():
            try:
                timestamp = int(time.time())
                conf_str = f"conf{confidence:.2f}_" if confidence is not None else ""
                audio_filename = f"{conf_str}recorded_{device_id}_{timestamp}.wav"
                audio_path = AUDIO_DIR / audio_filename

                from struct import pack
                with open(audio_path, "wb") as f:
                    data_size = len(audio_bytes)
                    f.write(b"RIFF")
                    f.write(pack("<I", 36 + data_size))
                    f.write(b"WAVE")
                    f.write(b"fmt ")
                    f.write(pack("<I", 16))
                    f.write(pack("<H", 1))
                    f.write(pack("<H", 1)) # mono
                    f.write(pack("<I", 16000)) # 16kHz
                    f.write(pack("<I", 16000 * 2)) # byte rate
                    f.write(pack("<H", 2)) # block align
                    f.write(pack("<H", 16)) # 16-bit
                    f.write(b"data")
                    f.write(pack("<I", data_size))
                    f.write(audio_bytes)
                logger.debug(f"Audio debug file saved: {audio_path}")
            except Exception as e:
                logger.error(f"Failed to save debug audio: {e}")

        # 使用 asyncio.to_thread 在背景儲存，不阻塞主流程
        if DEBUG_AUDIO_SAVE:
            asyncio.create_task(asyncio.to_thread(save_audio_file))
        else:
            logger.debug("Skipping audio debug file save (DEBUG_AUDIO_SAVE=0)")

        # --- 啟動 ASR (Faster-Whisper) ---
        t0 = time.time()
        text = await transcribe_audio(audio_base64, audio_format)
        metrics_ctx.record_latency("asr_latency", round(time.time() - t0, 3))
        metrics_ctx.mark_stage("asr_text", text)
        metrics_ctx.mark_stage("asr_text_length", len(text))
        
        if not text:
            metrics_ctx.set_flag("asr_empty", True)
            logger.info(f"ASR result is empty (Silence/Noise), skipping intent parsing for {device_id}")
            await play_local_sound("not_understood.wav")
            
            # Record & Return
            metrics_logger.log(metrics_ctx.finalize())
            aggregator.record(metrics_ctx)
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()
            
        logger.info(f"ASR result: {text}")

        # Parse intent with LLM (Will fallback to Keywords if clear match)
        t1 = time.time()
        intent = parse_intent_with_llm(text, metrics_ctx) # 需要修改此函式簽名
        metrics_ctx.record_latency("intent_latency", round(time.time() - t1, 3))

        if intent.get("action") == "unknown":
            await play_local_sound("not_understood.wav")
            # Record & Return
            metrics_logger.log(metrics_ctx.finalize())
            aggregator.record(metrics_ctx)
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()

        # Validate action
        action = intent.get("action", "relay_set")
        target = intent.get("target", "")
        value = intent.get("value", "")
        
        metrics_ctx.mark_stage("final_action", action)
        metrics_ctx.mark_stage("final_target", target)
        metrics_ctx.mark_stage("final_value", value)

        is_valid, error = action_validator.validate(action, target, value)
        if not is_valid:
            metrics_ctx.set_flag("validator_pass", False)
            metrics_ctx.mark_stage("reject_reason", error)
            await play_local_sound("error.wav")
            
            metrics_logger.log(metrics_ctx.finalize())
            aggregator.record(metrics_ctx)
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="error.wav"),
            ).model_dump()
            
        metrics_ctx.set_flag("validator_pass", True)

        await play_local_sound(get_action_sound(target, value))
        await dispatch_command(target, value, metrics_ctx)
        
        # Record Success
        metrics_logger.log(metrics_ctx.finalize())
        aggregator.record(metrics_ctx)
        
        return Action(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=ActionPayload(
                action=action,
                target=target,
                value=value,
                sound=get_action_sound(target, value),
            ),
        ).model_dump()

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        metrics_ctx.set_error(str(e))
        metrics_logger.log(metrics_ctx.finalize())
        aggregator.record(metrics_ctx)
        return Play(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=PlayPayload(audio="error.wav"),
        ).model_dump()


async def handle_audio_start(device_id: str, data: dict):
    """Signal clear buffer for new streaming session."""
    try:
        msg = AudioStreamStart(**data)
        manager.clear_audio_buffer(
            device_id, 
            confidence=msg.payload.confidence,
            transfer_mode=msg.payload.transfer_mode,
            total_samples=msg.payload.total_samples
        )
        logger.info(f"Stream start: {device_id} mode={msg.payload.transfer_mode}, total={msg.payload.total_samples}")
    except Exception as e:
        logger.error(f"Audio start error: {e}")


async def handle_audio_chunk(device_id: str, data: dict) -> Optional[dict]:
    """Receive chunk and process if is_last."""
    try:
        msg = AudioStreamChunk(**data)
        # Verify transfer mode
        if manager.transfer_modes.get(device_id) != "base64":
            logger.warning(f"Received Base64 chunk for {device_id} but mode is {manager.transfer_modes.get(device_id)}")
            
        chunk_data = base64.b64decode(msg.payload.data_base64)
        manager.append_audio_data(device_id, chunk_data)

        if msg.payload.is_last:
            return await process_stream_end(device_id)

        return None
    except Exception as e:
        logger.error(f"Audio chunk error: {e}")
        return None


async def process_stream_end(device_id: str) -> Optional[dict]:
    """Finalize and process audio buffer."""
    try:
        full_audio = manager.get_audio_data(device_id)
        full_audio_b64 = base64.b64encode(full_audio).decode("utf-8")
        # Get confidence before clearing
        confidence = manager.session_confidence.get(device_id)
        
        # Process first
        result = await process_complete_audio(
            device_id, full_audio_b64, "pcm_16k_16bit", confidence
        )
        
        # Then clear
        manager.clear_audio_buffer(device_id)
        return result
    except Exception as e:
        logger.error(f"Stream process error: {e}")
        manager.clear_audio_buffer(device_id)
        return None


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model
    logger.info("ESP-MIAO Server starting...")
    
    # Initialize MQTT
    try:
        logger.info(f"Connecting to MQTT Broker at {MQTT_BROKER}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        logger.error(f"MQTT Connection Error: {e}")

    # Initialize Whisper (Only if requested on start)
    if LOAD_MODEL_ON_START:
        try:
            get_whisper_model()
        except Exception as e:
            logger.error(f"Failed to load Whisper model on start: {e}")
    else:
        logger.info("Whisper model will be loaded lazily on first request.")

    logger.info(f"Devices registered: {[d.name for d in device_table.devices]}")
    logger.info(f"Allowed actions: {ALLOWED_ACTIONS}")
    # Ensure audio directory exists
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    # Start Metrics Logger
    init_metrics()
    
    yield
    
    logger.info("ESP-MIAO Server shutting down...")
    # Stop Metrics Logger
    shutdown_metrics()
    
    # Gracefully stop MQTT
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    logger.info("MQTT client stopped.")


app = FastAPI(
    title="ESP-MIAO Voice Agent Server",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "esp-miao",
        "devices": len(device_table.devices),
        "connected": manager.list_connected_devices(),
    }


@app.get("/devices")
async def list_devices():
    """List registered devices."""
    return device_table.model_dump()


@app.get("/devices/{device_name}")
async def get_device(device_name: str):
    """Get device by name."""
    device = device_table.get_device(device_name)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_name}")
    return device.model_dump()


@app.get("/shutdown")
async def shutdown():
    """優雅地關閉伺服器。"""
    logger.info("Shutdown requested via API...")
    import os
    import signal
    os.kill(os.getpid(), signal.SIGINT)
    return {"status": "shutting down"}


# --- Feedback Audio API ---
@app.get("/audio/{filename}")
async def get_audio(filename: str):
    """Serve feedback audio files."""
    audio_path = AUDIO_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio not found: {filename}")
    return FileResponse(audio_path, media_type="audio/wav")


@app.get("/audio")
async def list_audio():
    """List available audio files."""
    if not AUDIO_DIR.exists():
        return {"files": []}
    files = [f.name for f in AUDIO_DIR.glob("*.wav")]
    return {"files": files}


# --- WebSocket Endpoint ---
@app.websocket("/ws/{device_id}")
async def websocket_endpoint(websocket: WebSocket, device_id: str):
    """WebSocket endpoint for ESP32 communication."""
    await manager.connect(device_id, websocket)

    # --- 握手即同步 (Miao-Sync) ---
    # 當裝置連線時，立即發送伺服器當前時間，確保離線環境下時間一致
    now = time.time()
    sync_msg = TimeSync(
        device_id="server",
        timestamp=int(now * 1000),
        payload=TimeSyncPayload(
            seconds=int(now),
            ms=int((now - int(now)) * 1000)
        )
    )
    await websocket.send_text(json.dumps(sync_msg.model_dump()))
    logger.info(f"Sent TimeSync to {device_id}")

    try:
        while True:
            # Receive either text or bytes
            message = await websocket.receive()
            
            # Handle disconnection event
            if message["type"] == "websocket.disconnect":
                logger.info(f"Disconnect event for {device_id}")
                break

            if "text" in message:
                raw_msg = message["text"]
                try:
                    data = json.loads(raw_msg)
                    msg_type = data.get("type")
                    dev_ts = data.get("timestamp", 0)
                    
                    logger.debug(f"Received TEXT from {device_id} (TS: {dev_ts}): {raw_msg}")

                    response = None
                    if msg_type == "command_request":
                        response = await handle_command_request(device_id, data)
                    elif msg_type == "fallback_request":
                        response = await handle_fallback_request(device_id, data)
                    elif msg_type == "audio_request":
                        response = await handle_audio_request(device_id, data)
                    elif msg_type == "audio_start":
                        await handle_audio_start(device_id, data)
                        continue
                    elif msg_type == "audio_chunk":
                        response = await handle_audio_chunk(device_id, data)
                        if response is None:
                            continue
                    elif msg_type == "action_result":
                        logger.info(f"Action result from {device_id}: {data}")
                        manager.resolve_pending(device_id, data)
                        continue
                    else:
                        logger.warning(f"Unknown message type: {msg_type}")
                        continue

                    if response:
                        await websocket.send_text(json.dumps(response))

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
            
            elif "bytes" in message:
                chunk_data = message["bytes"]
                logger.debug(f"Received BINARY from {device_id}: {len(chunk_data)} bytes")
                
                if manager.transfer_modes.get(device_id) != "binary":
                    logger.warning(f"Received binary for {device_id} but mode is {manager.transfer_modes.get(device_id)}")
                
                manager.append_audio_data(device_id, chunk_data)
                
                # Check if we have received enough bytes
                expected = manager.expected_bytes.get(device_id, 0)
                current = len(manager.audio_buffers.get(device_id, []))
                
                if expected > 0 and current >= expected:
                    logger.info(f"Binary stream complete for {device_id} ({current}/{expected} bytes)")
                    response = await process_stream_end(device_id)
                    if response:
                        await websocket.send_text(json.dumps(response))
            
            else:
                logger.debug(f"Ignored WebSocket message: {message.get('type')}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error in {device_id}: {e}")
    finally:
        manager.disconnect(device_id)


def main():
    """Run server with uvicorn."""
    import uvicorn
    import os

    # 讀取環境變數，預設關閉 reload 以節省 RPi4 資源
    reload_enabled = os.getenv("SERVER_RELOAD", "0") == "1"
    
    logger.info(f"Starting server (reload={'enabled' if reload_enabled else 'disabled'})...")

    uvicorn.run(
        "esp_miao.server:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        reload_dirs=["src"] if reload_enabled else None, # 即使開啟也只監控 Python 原始碼
        log_level="info",
    )


if __name__ == "__main__":
    main()
