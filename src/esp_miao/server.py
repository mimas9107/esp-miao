"""ESP-MIAO FastAPI WebSocket Server

Handles ESP32 voice agent communication and LLM intent parsing.
"""

import asyncio
import base64
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
import ollama

from .models import (
    Action,
    ActionPayload,
    ActionValidator,
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

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        logger.info(f"Device connected: {device_id}")

    def disconnect(self, device_id: str):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
            logger.info(f"Device disconnected: {device_id}")
        # Cancel any pending futures
        if device_id in self.pending_responses:
            self.pending_responses[device_id].cancel()
            del self.pending_responses[device_id]

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


# --- ASR Pipeline (Placeholder) ---
async def transcribe_audio(
    audio_base64: str, audio_format: str = "pcm_16k_16bit"
) -> str:
    """
    Transcribe audio to text.
    TODO: Integrate with Whisper or other ASR service.
    """
    logger.info(
        f"ASR: Received audio ({len(audio_base64)} bytes base64, format={audio_format})"
    )
    # Placeholder - in production, integrate with:
    # - OpenAI Whisper API
    # - Local Whisper model
    # - Other ASR services
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
    "on": ["開", "打開", "開啟", "啟動", "turn on", "on", "open"],
    "off": ["關", "關閉", "關掉", "停止", "turn off", "off", "close"],
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

    # 如果關鍵字無法識別，直接返回 unknown
    if keyword_intent["action"] == "unknown":
        logger.info(f"No matching device in text: {text}")
        return {"action": "unknown", "target": "", "value": ""}

    # 使用 LLM 解析
    prompt = f"""你是智慧家庭控制系統。將指令轉成 JSON。

可控制裝置：{device_names}

指令：{text}

只輸出一行 JSON：
{{"action": "relay_set", "target": "裝置名", "value": "on或off"}}
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

        # 驗證 LLM 結果：target 必須在裝置列表中
        if result.get("target") not in device_names:
            logger.warning(
                f"LLM returned invalid target '{result.get('target')}', using keyword result"
            )
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


# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ESP-MIAO Server starting...")
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
