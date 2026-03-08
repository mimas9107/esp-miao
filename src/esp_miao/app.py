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

from .models import (
    Action,
    ActionPayload,
    AudioRequest,
    AudioStreamStart,
    AudioStreamChunk,
    CommandRequest,
    FallbackRequest,
    Play,
    PlayPayload,
    TimeSync,
    TimeSyncPayload,
    ALLOWED_ACTIONS,
    COMMAND_MAP,
)

from .config import (
    LOAD_MODEL_ON_START,
    DEBUG_AUDIO_SAVE,
    LOG_LEVEL,
    AUDIO_DIR,
    LOCAL_SOUND_DIR,
)

from .connection import (
    mqtt_client,
    device_table,
    manager,
    action_validator,
    MQTT_BROKER,
    MQTT_PORT,
)

from .utils import play_local_sound, get_action_sound
from .dispatch import dispatch_command
from .intent import parse_intent_with_llm
from .audio import transcribe_audio, get_whisper_model
from .metrics import init_metrics, shutdown_metrics, metrics_logger, aggregator, MetricsContext
from .version import __version__

# --- Logging setup ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("esp-miao.app")

# --- Message Handlers ---
async def handle_command_request(device_id: str, data: dict) -> dict:
    """Handle local command from esp-sr."""
    try:
        msg = CommandRequest(**data)
        cmd_id = msg.payload.cmd_id

        if cmd_id in COMMAND_MAP:
            cmd_name, target, value = COMMAND_MAP[cmd_id]
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
        intent = parse_intent_with_llm(text, metrics_ctx)
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
    logger.info(f"ESP-MIAO Server v{__version__} starting...")
    
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
    version=__version__,
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "esp-miao",
        "version": __version__,
        "devices": len(device_table.devices),
        "connected": manager.list_connected_devices(),
    }


@app.get("/devices")
async def list_devices():
    """List registered devices."""
    return [d.model_dump() for d in device_table.devices]


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

@app.get("/ack")
async def ack():
    """Ack reply after wake up. """
    await play_local_sound("ack.wav")
    return {"status": "ack"}


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
