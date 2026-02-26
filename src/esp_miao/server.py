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
    ALLOWED_ACTIONS,
)

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("esp-miao")


# --- Configuration ---
AUDIO_DIR = Path(__file__).parent / "audio"
TIMEOUT_SECONDS = 10.0  # WebSocket response timeout


# --- Device Table ---
device_table = DeviceTable(
    devices=[
        Device(name="light", type="relay", gpio=26),
        Device(name="fan", type="relay", gpio=27),
        Device(name="led", type="led", gpio=2),
    ]
)

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
        # Cancel any pending futures
        if device_id in self.pending_responses:
            self.pending_responses[device_id].cancel()
            del self.pending_responses[device_id]

    def clear_audio_buffer(self, device_id: str, confidence: Optional[float] = None):
        """Clear the audio buffer for a device and set session confidence."""
        if device_id in self.audio_buffers:
            self.audio_buffers[device_id] = bytearray()
        
        if confidence is not None:
            self.session_confidence[device_id] = confidence
        else:
            self.session_confidence.pop(device_id, None)
            
        logger.debug(f"Cleared audio buffer for {device_id}, confidence: {confidence}")

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
    global whisper_model
    if whisper_model is None:
        logger.error("Whisper model not initialized")
        return ""

    try:
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(audio_base64)
        
        # Load audio data as a stream
        # Faster-whisper can take a file path or a binary stream
        # Note: it needs to know the format if it's raw PCM
        # Since faster-whisper/ctranslate2 usually expects a file with header or 
        # numpy array, we might need to wrap it.
        
        # For simplicity, we'll use the temporary WAV file approach if direct stream fails
        # but let's try passing the bytes through io.BytesIO
        
        # Actually, let's use a temporary file to be safe with formats
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            # Write simple WAV header
            from struct import pack
            sample_rate = 16000
            bits_per_sample = 16
            channels = 1
            data_size = len(audio_bytes)
            
            tmp.write(b"RIFF")
            tmp.write(pack("<I", 36 + data_size))
            tmp.write(b"WAVE")
            tmp.write(b"fmt ")
            tmp.write(pack("<I", 16))
            tmp.write(pack("<H", 1))
            tmp.write(pack("<H", channels))
            tmp.write(pack("<I", sample_rate))
            tmp.write(pack("<I", sample_rate * channels * (bits_per_sample // 8)))
            tmp.write(pack("<H", channels * (bits_per_sample // 8)))
            tmp.write(pack("<H", bits_per_sample))
            tmp.write(b"data")
            tmp.write(pack("<I", data_size))
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # Force language to 'zh' (Chinese) for better accuracy in this context
            segments, info = whisper_model.transcribe(
                tmp_path, 
                beam_size=5, 
                language="zh",
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )
            
            text_segments = []
            import re
            
            for segment in segments:
                # 檢查每個片段的無聲機率
                if segment.no_speech_prob < 0.7:
                    # 強化重複幻聽模式過濾 (例如 "哈哈哈哈" 或 "我認識了我認識了")
                    clean_text = segment.text.strip()
                    # 只要長度大於等於 4 且有明顯重複模式就攔截
                    if len(clean_text) >= 4:
                        # 檢查後半段是否重複前半段
                        half = len(clean_text) // 2
                        if clean_text[:half] == clean_text[half:]:
                            logger.info(f"Filtered out repetitive hallucination: '{clean_text}'")
                            continue
                        # 檢查連續四個字是否相同 (如 "哈哈哈哈")
                        if len(clean_text) >= 4 and all(c == clean_text[0] for c in clean_text[:4]):
                            logger.info(f"Filtered out repetitive character hallucination: '{clean_text}'")
                            continue
                    text_segments.append(clean_text)
                else:
                    logger.info(f"Filtered out hallucination segment: '{segment.text}' (no_speech_prob: {segment.no_speech_prob:.2f})")
            
            text = "".join(text_segments).strip()
            logger.info(f"ASR (Whisper) [{info.language}]: {text}")
            return text
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        logger.error(f"ASR error: {e}")
        return ""


# --- LLM Intent Parsing ---

# 裝置別名映射（支援使用者各種說法）
DEVICE_ALIASES: dict[str, list[str]] = {
    "light": ["燈", "電燈", "燈光", "lights", "light"],
    "fan": ["風扇", "電風扇", "電扇", "fans", "fan"],
    "led": ["led", "LED", "指示燈"],
}

# 動作關鍵字
ACTION_KEYWORDS: dict[str, list[str]] = {
    "on": ["開", "打開", "開啟", "啟動", "turn on", "on", "open", "kaitan"],
    "off": ["關", "關閉", "關掉", "停止", "turn off", "off", "close", "kuan teng"],
}


def extract_intent_from_text(text: str) -> dict:
    """
    使用關鍵字匹配從文字中提取意圖。
    這是 LLM 的後備方案，確保即使 LLM 回傳錯誤結果也能正確處理。
    """
    text_lower = text.lower()

    # 找出目標裝置
    target = None
    for device_name, aliases in DEVICE_ALIASES.items():
        for alias in aliases:
            if alias in text or alias.lower() in text_lower:
                target = device_name
                break
        if target:
            break

    # 找出動作
    value = None
    for action_value, keywords in ACTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text or keyword.lower() in text_lower:
                value = action_value
                break
        if value:
            break

    if target and value:
        return {"action": "relay_set", "target": target, "value": value}

    return {"action": "unknown", "target": "", "value": ""}


def parse_intent_with_llm(text: str) -> dict:
    """Use Ollama LLM to parse natural language intent with fallback validation."""
    device_names = [d.name for d in device_table.devices]

    # 先用關鍵字匹配提取意圖（作為驗證基準）
    keyword_intent = extract_intent_from_text(text)
    logger.debug(f"Keyword extraction: {text} -> {keyword_intent}")
    
    # 方案 A: 關鍵字攔截層 (Keyword Pre-filter)
    # 如果內容完全沒提到裝置也沒有動作，不送 LLM，直接回傳 unknown
    if keyword_intent["action"] == "unknown":
        logger.info(f"Pre-filter: No keywords found in '{text}', skipping LLM.")
        return keyword_intent

    # 方案 B: 優化 LLM Prompt
    prompt = f"""Task: Convert voice command to JSON.
Available devices: {device_names}

Examples:
- Command: "幫我開燈" -> {{"action": "relay_set", "target": "light", "value": "on"}}
- Command: "關掉風扇" -> {{"action": "relay_set", "target": "fan", "value": "off"}}
- Command: "哈哈笑" -> {{"action": "unknown", "target": "", "value": ""}}
- Command: "哎呀乖乖" -> {{"action": "unknown", "target": "", "value": ""}}

Command: "{text}"
Response in ONE LINE JSON format ONLY:
"""

    try:
        response = ollama.generate(model="qwen2.5:0.5b", prompt=prompt)
        result_text = response["response"]

        # Extract JSON from response
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        # 找出 JSON 部分
        import re

        json_match = re.search(r"\{[^}]+\}", result_text)
        if json_match:
            result_text = json_match.group()

        result = json.loads(result_text.strip())
        logger.info(f"LLM parsed: {text} -> {result}")

        # 驗證邏輯：如果 LLM 結果無效，使用關鍵字結果
        if result.get("target") not in device_names or result.get("value") not in ["on", "off"]:
            logger.warning(f"LLM output invalid, falling back to keywords")
            return keyword_intent
            
        # 交叉驗證：如果關鍵字能精確識別出 target/value 但與 LLM 不同，以關鍵字為主
        if keyword_intent["action"] != "unknown":
            if result.get("target") != keyword_intent["target"] or result.get("value") != keyword_intent["value"]:
                logger.warning(f"LLM disagreed with keywords, prioritizing keywords: {keyword_intent}")
                return keyword_intent

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
                return Play(
                    device_id=device_id,
                    timestamp=int(time.time() * 1000),
                    payload=PlayPayload(audio="error.wav"),
                ).model_dump()

            return Action(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=ActionPayload(
                    action="relay_set",
                    target=target,
                    value=value,
                    sound="success.wav",
                ),
            ).model_dump()
        else:
            logger.warning(f"Unknown command ID: {cmd_id}")
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
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()

        logger.info(f"Fallback request: {text}")
        intent = parse_intent_with_llm(text)

        if intent.get("action") == "unknown":
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
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="error.wav"),
            ).model_dump()

        return Action(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=ActionPayload(
                action=action,
                target=target,
                value=value,
                sound="success.wav",
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
    try:
        # Decode base64 audio and save to file
        audio_bytes = base64.b64decode(audio_base64)
        
        # If confidence not provided, try to get from session
        if confidence is None:
            confidence = manager.session_confidence.get(device_id)

        logger.info(f" Audio processing: {len(audio_bytes)} bytes (confidence: {confidence})")

        # Save audio file for debugging/processing
        timestamp = int(time.time())
        conf_str = f"conf{confidence:.2f}_" if confidence is not None else ""
        audio_filename = f"{conf_str}recorded_{device_id}_{timestamp}.wav"
        audio_path = AUDIO_DIR / audio_filename

        # Write WAV header + PCM data
        from struct import pack

        with open(audio_path, "wb") as f:
            sample_rate = 16000
            bits_per_sample = 16
            channels = 1
            data_size = len(audio_bytes)
            file_size = 44 + data_size

            f.write(b"RIFF")
            f.write(pack("<I", file_size - 8))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(pack("<I", 16))
            f.write(pack("<H", 1))
            f.write(pack("<H", channels))
            f.write(pack("<I", sample_rate))
            f.write(pack("<I", sample_rate * channels * (bits_per_sample // 8)))
            f.write(pack("<H", channels * (bits_per_sample // 8)))
            f.write(pack("<H", bits_per_sample))
            f.write(b"data")
            f.write(pack("<I", data_size))
            f.write(audio_bytes)

        logger.info(f"Audio saved to: {audio_path}")

        # Transcribe audio to text
        text = await transcribe_audio(audio_base64, audio_format)
        
        if not text:
            logger.info(f"ASR result is empty (Silence/Noise), skipping intent parsing for {device_id}")
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()
            
        logger.info(f"ASR result: {text}")

        # Parse intent with LLM
        intent = parse_intent_with_llm(text)

        if intent.get("action") == "unknown":
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="not_understood.wav"),
            ).model_dump()

        # Validate action
        action = intent.get("action", "relay_set")
        target = intent.get("target", "")
        value = intent.get("value", "")

        is_valid, error = action_validator.validate(action, target, value)
        if not is_valid:
            return Play(
                device_id=device_id,
                timestamp=int(time.time() * 1000),
                payload=PlayPayload(audio="error.wav"),
            ).model_dump()

        return Action(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=ActionPayload(
                action=action,
                target=target,
                value=value,
                sound="success.wav",
            ),
        ).model_dump()

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        return Play(
            device_id=device_id,
            timestamp=int(time.time() * 1000),
            payload=PlayPayload(audio="error.wav"),
        ).model_dump()


async def handle_audio_start(device_id: str, data: dict):
    """Signal clear buffer for new streaming session."""
    try:
        msg = AudioStreamStart(**data)
        manager.clear_audio_buffer(device_id, confidence=msg.payload.confidence)
        logger.info(f"Stream start: {device_id} expecting {msg.payload.total_samples}, confidence: {msg.payload.confidence}")
    except Exception as e:
        logger.error(f"Audio start error: {e}")


async def handle_audio_chunk(device_id: str, data: dict) -> Optional[dict]:
    """Receive chunk and process if is_last."""
    try:
        msg = AudioStreamChunk(**data)
        chunk_data = base64.b64decode(msg.payload.data_base64)
        manager.append_audio_data(device_id, chunk_data)

        if msg.payload.is_last:
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

        return None
    except Exception as e:
        logger.error(f"Audio chunk error: {e}")
        return None


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global whisper_model
    logger.info("ESP-MIAO Server starting...")
    
    # Initialize Whisper
    try:
        logger.info("Initializing Whisper model (base, cpu)...")
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")

    logger.info(f"Devices registered: {[d.name for d in device_table.devices]}")
    logger.info(f"Allowed actions: {ALLOWED_ACTIONS}")
    # Ensure audio directory exists
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    yield
    logger.info("ESP-MIAO Server shutting down...")


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

    try:
        while True:
            raw_msg = await websocket.receive_text()
            logger.debug(f"Received from {device_id}: {raw_msg}")

            try:
                data = json.loads(raw_msg)
                msg_type = data.get("type")

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
                    # Resolve pending future if waiting
                    manager.resolve_pending(device_id, data)
                    continue  # No response needed
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    continue

                await websocket.send_text(json.dumps(response))

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")

    except WebSocketDisconnect:
        manager.disconnect(device_id)


def main():
    """Run server with uvicorn."""
    import uvicorn

    uvicorn.run(
        "esp_miao.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
