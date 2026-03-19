import logging
import json
import asyncio
import paho.mqtt.client as mqtt
from typing import Optional
from fastapi import WebSocket
from .models import Device, DeviceTable, ActionValidator
from .config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_DISCOVERY_TOPIC,
    MQTT_AUTH_USER, MQTT_AUTH_PASSWORD, TIMEOUT_SECONDS, ACTION_KEYWORDS
)

logger = logging.getLogger("esp-miao.connection")

# --- Device & Discovery Support ---
class DynamicDeviceTable:
    def __init__(self, devices: list[Device] = None):
        self._devices: dict[str, Device] = {d.name: d for d in (devices or [])}
        self._aliases: dict[str, str] = {} # alias -> device_name
        self._action_keyword_map: dict[str, dict[str, list[str]]] = {} # device_name -> {on: [], off: []}
        self._update_aliases()

    def _update_aliases(self):
        """Rebuild alias map from current devices."""
        self._aliases = {}
        # Add dynamic aliases from discovered devices
        for dev in self._devices.values():
            if dev.aliases:
                for alias in dev.aliases:
                    self._aliases[alias.lower()] = dev.name

    def update_device(self, dev_info: dict):
        """Register or update a device from MQTT discovery."""
        name = dev_info.get("name") or dev_info.get("device_id")
        if not name:
            logger.warning("Received discovery payload without name/device_id")
            return
        
        dev_type = dev_info.get("type") or dev_info.get("device_type", "unknown")
        action_kws = dev_info.get("action_keywords")
        
        new_dev = Device(
            name=name,
            type=dev_type,
            gpio=dev_info.get("gpio"),
            aliases=dev_info.get("aliases", []),
            control_topic=dev_info.get("control_topic", MQTT_TOPIC),
            commands=dev_info.get("commands", {"on": "ON", "off": "OFF"}),
            action_keywords=action_kws
        )
        self._devices[name] = new_dev
        
        # Update action keyword map if provided
        if action_kws:
            self._action_keyword_map[name] = action_kws
            logger.info(f"Custom action keywords registered for {name}")

        self._update_aliases()
        logger.info(f"Device registered/updated: {name} ({new_dev.type})")

    def remove_device(self, name: str):
        """Remove device from table (e.g., on LWT offline)."""
        if name in self._devices:
            del self._devices[name]
            if name in self._action_keyword_map:
                del self._action_keyword_map[name]
            self._update_aliases()
            logger.info(f"Device removed: {name}")
        else:
            logger.warning(f"remove_device: '{name}' not found in table")

    def get_action_keywords(self, device_name: str) -> dict[str, list[str]]:
        """Get action keywords for device, fallback to global defaults."""
        return self._action_keyword_map.get(device_name, ACTION_KEYWORDS)

    @property
    def devices(self) -> list[Device]:
        return list(self._devices.values())

    @property
    def alias_map(self) -> dict[str, str]:
        return self._aliases

    def get_device(self, name: str) -> Optional[Device]:
        return self._devices.get(name)

# Initialize with an empty table (Discovery-first)
device_table = DynamicDeviceTable()

# --- Action Validator (Safety) ---
action_validator = ActionValidator(device_table)

# --- MQTT Setup ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

if MQTT_AUTH_USER and MQTT_AUTH_PASSWORD:
    mqtt_client.username_pw_set(MQTT_AUTH_USER, MQTT_AUTH_PASSWORD)

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_DISCOVERY_TOPIC)
        client.subscribe("home/+/status")
        logger.info(f"Subscribed to discovery ({MQTT_DISCOVERY_TOPIC}) and status topics")
    else:
        logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages for discovery and status."""
    logger.info(f"Received MQTT message on topic: {msg.topic}")
    try:
        if msg.topic == MQTT_DISCOVERY_TOPIC:
            payload = json.loads(msg.payload.decode())
            logger.info(f"Processing discovery payload: {payload}")
            device_table.update_device(payload)
        elif msg.topic.endswith("/status"):
            payload = json.loads(msg.payload.decode())
            logger.info(f"Processing status payload: {payload}")
            if payload.get("status") == "offline":
                device_id = payload.get("device_id")
                if device_id:
                    device_table.remove_device(device_id)
            elif payload.get("status") == "online":
                logger.info(f"Device online: {payload.get('device_id')}")
    except Exception as e:
        logger.warning(f"MQTT message processing error on topic {msg.topic}: {e}")

mqtt_client.on_connect = on_connect

def on_log(client, userdata, level, buf):
    """MQTT Internal Log Handler."""
    logger.debug(f"MQTT Log: {buf}")

mqtt_client.on_log = on_log
mqtt_client.on_message = on_message

# --- Connection Manager (WebSocket) ---
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
