"""Pydantic models for ESP-MIAO JSON Protocol

Based on SPEC.md protocol definitions.
"""

from enum import Enum
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


# --- ESP32 State Machine (SPEC.md 2.1) ---


class ESP32State(str, Enum):
    """ESP32 state machine states."""

    IDLE = "IDLE"  # Standby waiting wake
    WAKE = "WAKE"  # Wake word detected
    LISTEN = "LISTEN"  # Capturing command
    RECOGNIZE = "RECOGNIZE"  # esp-sr processing
    LOCAL_EXECUTE = "LOCAL_EXECUTE"  # Execute local action
    FORWARD_SERVER = "FORWARD_SERVER"  # Send to server
    WAIT_ACTION = "WAIT_ACTION"  # Waiting server response
    PLAY_FEEDBACK = "PLAY_FEEDBACK"  # Play audio feedback
    ERROR = "ERROR"  # Error handling


# --- Event Types (SPEC.md 2.2) ---


class EventType(str, Enum):
    """Event types for ESP32-Server communication."""

    WAKE_DETECTED = "wake_detected"  # Wake word hit (esp-sr)
    COMMAND_LOCAL = "command_local"  # Local command matched (esp-sr)
    COMMAND_UNKNOWN = "command_unknown"  # No local match (esp-sr)
    ACTION_EXECUTE = "action_execute"  # Action instruction (server)
    ACTION_RESULT = "action_result"  # Execution result (esp32)
    PLAY_AUDIO = "play_audio"  # Feedback audio (server)
    ERROR = "error"  # Error condition (both)


# --- Command Mapping (SPEC.md 4.5) ---


class Command(int, Enum):
    """MultiNet command IDs."""

    LIGHT_ON = 0
    LIGHT_OFF = 1
    FAN_ON = 2
    FAN_OFF = 3
    UNKNOWN = -1


# Command ID to (name, target, value) mapping
COMMAND_MAP: dict[int, tuple[str, str, str]] = {
    Command.LIGHT_ON: ("LIGHT_ON", "light", "on"),
    Command.LIGHT_OFF: ("LIGHT_OFF", "light", "off"),
    Command.FAN_ON: ("FAN_ON", "fan", "on"),
    Command.FAN_OFF: ("FAN_OFF", "fan", "off"),
}


def map_command(cmd_id: int) -> tuple[str, str, str]:
    """Map command ID to (name, target, value)."""
    return COMMAND_MAP.get(cmd_id, ("UNKNOWN", "", ""))


# --- Safety: GPIO Whitelist ---

# ESP32 safe GPIO pins (避免 flash/boot pins)
GPIO_WHITELIST: set[int] = {
    2,
    4,
    5,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    21,
    22,
    23,
    25,
    26,
    27,
    32,
    33,
}

# Allowed actions for validation
ALLOWED_ACTIONS: set[str] = {"relay_set", "led_set", "play_sound", "noop"}

# Allowed values for relay/led
ALLOWED_VALUES: set[str] = {"on", "off", "toggle"}


# --- Common Envelope ---


class BaseMessage(BaseModel):
    """Common envelope for all messages."""

    device_id: str = Field(..., description="Device identifier")
    timestamp: int = Field(..., description="Unix timestamp or device uptime ms")


# --- ESP32 -> Server Messages ---


class CommandRequestPayload(BaseModel):
    """Payload for command_request from esp-sr."""

    source: Literal["esp-sr"] = "esp-sr"
    cmd_id: int = Field(..., description="Command ID from MultiNet")
    cmd_name: str = Field(..., description="Command name mapping")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Recognition confidence")


class CommandRequest(BaseMessage):
    """ESP32 sends recognized command to server."""

    type: Literal["command_request"] = "command_request"
    payload: CommandRequestPayload


class FallbackRequestPayload(BaseModel):
    """Payload for fallback_request when esp-sr cannot match."""

    text: Optional[str] = Field(None, description="Raw text or audio transcription")
    audio_base64: Optional[str] = Field(None, description="Base64 encoded PCM audio")
    audio_format: Optional[str] = Field("pcm_16k_16bit", description="Audio format")


class FallbackRequest(BaseMessage):
    """ESP32 sends fallback request for LLM processing."""

    type: Literal["fallback_request"] = "fallback_request"
    payload: FallbackRequestPayload


class AudioRequestPayload(BaseModel):
    """Payload for audio_request with recorded PCM audio."""

    audio_base64: str = Field(..., description="Base64 encoded PCM audio")
    audio_format: str = Field("pcm_16k_16bit", description="Audio format")
    duration_ms: int = Field(
        ..., description="Audio duration in ms (e.g., 3000 for 3s)"
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Wake word confidence")


class AudioRequest(BaseMessage):
    """ESP32 sends recorded audio to server for processing."""

    type: Literal["audio_request"] = "audio_request"
    payload: AudioRequestPayload


class AudioStreamStartPayload(BaseModel):
    """Payload to start a chunked audio stream."""

    audio_format: str = Field("pcm_16k_16bit", description="Audio format")
    total_samples: int = Field(..., description="Total expected samples")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Wake word confidence")


class AudioStreamStart(BaseMessage):
    """ESP32 signals start of audio stream."""

    type: Literal["audio_start"] = "audio_start"
    payload: AudioStreamStartPayload


class AudioStreamChunkPayload(BaseModel):
    """Payload for a single audio chunk."""

    chunk_index: int = Field(..., description="Index of the chunk")
    is_last: bool = Field(False, description="Whether this is the last chunk")
    data_base64: str = Field(..., description="Base64 encoded PCM chunk")


class AudioStreamChunk(BaseMessage):
    """ESP32 sends an audio chunk."""

    type: Literal["audio_chunk"] = "audio_chunk"
    payload: AudioStreamChunkPayload


class ActionResultPayload(BaseModel):
    """Payload for action execution result."""

    status: Literal["success", "failure"] = Field(..., description="Execution status")
    error: Optional[str] = Field(None, description="Error message if failed")


class ActionResult(BaseMessage):
    """ESP32 reports action execution result."""

    type: Literal["action_result"] = "action_result"
    payload: ActionResultPayload


# --- Server -> ESP32 Messages ---


class ActionPayload(BaseModel):
    """Payload for action command to ESP32."""

    action: str = Field(..., description="Action type: relay_set, led_set, etc.")
    target: str = Field(..., description="Target device: light, fan, etc.")
    value: str = Field(..., description="Value: on, off, toggle, etc.")
    sound: Optional[str] = Field(None, description="Feedback sound file to play")


class Action(BaseMessage):
    """Server sends action command to ESP32."""

    type: Literal["action"] = "action"
    payload: ActionPayload


class PlayPayload(BaseModel):
    """Payload for audio playback command."""

    audio: str = Field(..., description="Audio file to play")


class Play(BaseMessage):
    """Server sends audio playback command."""

    type: Literal["play"] = "play"
    payload: PlayPayload


# --- Type unions for parsing ---

ESP32ToServerMessage = Union[
    CommandRequest, FallbackRequest, AudioRequest, ActionResult
]
ServerToESP32Message = Union[Action, Play]


# --- Device Table ---


class Device(BaseModel):
    """Device definition in device table."""

    name: str = Field(..., description="Device name")
    type: Literal["relay", "led", "sensor"] = Field(..., description="Device type")
    gpio: int = Field(..., description="GPIO pin number")

    @field_validator("gpio")
    @classmethod
    def validate_gpio_whitelist(cls, v: int) -> int:
        """Validate GPIO is in whitelist for safety."""
        if v not in GPIO_WHITELIST:
            raise ValueError(f"GPIO {v} not in whitelist: {sorted(GPIO_WHITELIST)}")
        return v


class DeviceTable(BaseModel):
    """Device table managed by server."""

    devices: list[Device] = Field(default_factory=list)

    def get_device(self, name: str) -> Optional[Device]:
        """Get device by name."""
        for d in self.devices:
            if d.name == name:
                return d
        return None

    def get_gpio(self, name: str) -> Optional[int]:
        """Get GPIO pin for device."""
        device = self.get_device(name)
        return device.gpio if device else None


# --- Safety: Action Validation ---


class ActionValidator:
    """Validate actions before sending to ESP32."""

    def __init__(self, device_table: DeviceTable):
        self.device_table = device_table

    def validate(self, action: str, target: str, value: str) -> tuple[bool, str]:
        """
        Validate action is safe to execute.
        Returns (is_valid, error_message).
        """
        # Check action type
        if action not in ALLOWED_ACTIONS:
            return False, f"Action '{action}' not allowed. Use: {ALLOWED_ACTIONS}"

        # noop is always valid
        if action == "noop":
            return True, ""

        # Check target exists
        device = self.device_table.get_device(target)
        if device is None:
            return False, f"Unknown target device: {target}"

        # Check value
        if action in ("relay_set", "led_set") and value not in ALLOWED_VALUES:
            return False, f"Value '{value}' not allowed. Use: {ALLOWED_VALUES}"

        return True, ""

    def validate_or_failsafe(
        self, action: str, target: str, value: str
    ) -> tuple[str, str, str]:
        """
        Validate and return safe action. If invalid, return fail-safe (noop).
        """
        is_valid, error = self.validate(action, target, value)
        if not is_valid:
            return "noop", "", ""
        return action, target, value
