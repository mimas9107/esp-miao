#!/usr/bin/env python3
"""ESP32 Simulator for testing WebSocket communication.

Updated 2026-03-05: Added time_sync support and fixed attribute errors.
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

try:
    import websockets
except ImportError:
    print("Error: websockets not installed. Run: uv add websockets")
    sys.exit(1)


# --- ANSI Colors for CLI output ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def color(text: str, c: str) -> str:
    return f"{c}{text}{Colors.ENDC}"


# --- ESP32 State Machine (from SPEC.md 2.1) ---
class State(str, Enum):
    IDLE = "IDLE"
    WAKE = "WAKE"
    LISTEN = "LISTEN"
    RECOGNIZE = "RECOGNIZE"
    LOCAL_EXECUTE = "LOCAL_EXECUTE"
    FORWARD_SERVER = "FORWARD_SERVER"
    WAIT_ACTION = "WAIT_ACTION"
    PLAY_FEEDBACK = "PLAY_FEEDBACK"
    ERROR = "ERROR"


# --- Command Mapping (from SPEC.md 4.5) ---
COMMANDS = {
    0: ("LIGHT_ON", "light", "on"),
    1: ("LIGHT_OFF", "light", "off"),
    2: ("FAN_ON", "fan", "on"),
    3: ("FAN_OFF", "fan", "off"),
}


@dataclass
class SimulatorConfig:
    device_id: str = "esp32_01"
    host: str = "localhost"
    port: int = 8000


class ESP32Simulator:
    """Simulates ESP32 device with state machine and WebSocket communication."""

    def __init__(self, config: SimulatorConfig):
        self.config = config
        self.state = State.IDLE
        self.ws = None
        self.running = False
        self.msg_queue = asyncio.Queue()
        self.reader_task = None

    @property
    def ws_uri(self) -> str:
        return f"ws://{self.config.host}:{self.config.port}/ws/{self.config.device_id}"

    def log(self, msg: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        state_color = {
            State.IDLE: Colors.DIM,
            State.WAKE: Colors.YELLOW,
            State.LISTEN: Colors.CYAN,
            State.RECOGNIZE: Colors.BLUE,
            State.LOCAL_EXECUTE: Colors.GREEN,
            State.FORWARD_SERVER: Colors.BLUE,
            State.WAIT_ACTION: Colors.YELLOW,
            State.PLAY_FEEDBACK: Colors.GREEN,
            State.ERROR: Colors.RED,
        }.get(self.state, Colors.ENDC)

        level_color = {
            "INFO": Colors.BLUE,
            "SEND": Colors.GREEN,
            "RECV": Colors.CYAN,
            "STATE": Colors.YELLOW,
            "ERROR": Colors.RED,
        }.get(level, Colors.ENDC)

        print(
            f"{Colors.DIM}[{timestamp}]{Colors.ENDC} "
            f"{state_color}[{self.state.value:^15}]{Colors.ENDC} "
            f"{level_color}{level:>5}{Colors.ENDC}: {msg}"
        )

    def set_state(self, new_state: State):
        old_state = self.state
        self.state = new_state
        self.log(f"{old_state.value} -> {new_state.value}", "STATE")

    def get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)

    async def send_message(self, msg: dict):
        """Send JSON message to server."""
        if self.ws:
            json_str = json.dumps(msg, ensure_ascii=False)
            self.log(f">>> {json_str}", "SEND")
            await self.ws.send(json_str)

    async def _reader_loop(self):
        """Background loop to read from websocket."""
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                self.log(f"<<< {raw}", "RECV")
                
                # Auto handle system messages
                if msg.get("type") == "time_sync":
                    self.handle_time_sync(msg)
                else:
                    await self.msg_queue.put(msg)
        except Exception as e:
            if self.running:
                self.log(f"Reader loop error: {e}", "ERROR")

    async def receive_message(self, timeout: float = 10.0) -> dict:
        """Receive message from queue."""
        try:
            return await asyncio.wait_for(self.msg_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return {}

    # --- Protocol Messages ---

    def make_command_request(self, cmd_id: int, confidence: float = 0.95) -> dict:
        """Create command_request message."""
        cmd_name, _, _ = COMMANDS.get(cmd_id, ("UNKNOWN", "", ""))
        return {
            "type": "command_request",
            "device_id": self.config.device_id,
            "timestamp": self.get_timestamp(),
            "payload": {
                "source": "esp-sr",
                "cmd_id": cmd_id,
                "cmd_name": cmd_name,
                "confidence": confidence,
            },
        }

    def make_fallback_request(self, text: str) -> dict:
        """Create fallback_request message."""
        return {
            "type": "fallback_request",
            "device_id": self.config.device_id,
            "timestamp": self.get_timestamp(),
            "payload": {"text": text},
        }

    def make_audio_request(self, audio_base64: str, duration_ms: int = 3000) -> dict:
        """Create audio_request message."""
        return {
            "type": "audio_request",
            "device_id": self.config.device_id,
            "timestamp": self.get_timestamp(),
            "payload": {
                "audio_base64": audio_base64,
                "audio_format": "pcm_16k_16bit",
                "duration_ms": duration_ms,
            },
        }

    def make_action_result(self, success: bool, error: str = None) -> dict:
        return {
            "type": "action_result",
            "device_id": self.config.device_id,
            "timestamp": self.get_timestamp(),
            "payload": {"status": "success" if success else "failure", "error": error},
        }

    # --- Action Handlers ---

    def handle_time_sync(self, msg: dict):
        payload = msg.get("payload", {})
        self.log(f"Time synchronized with server: {payload.get('seconds')}", "INFO")

    async def handle_action(self, msg: dict) -> bool:
        payload = msg.get("payload", {})
        action = payload.get("action", "")
        target = payload.get("target", "")
        value = payload.get("value", "")
        sound = payload.get("sound", "")

        self.log(f"Executing: {action}({target}={value})", "INFO")

        if action == "relay_set":
            self.log(f"[RELAY] {target} -> {value}", "INFO")
        elif action == "led_set":
            self.log(f"[LED] {target} -> {value}", "INFO")
        elif action == "noop":
            self.log("[NOOP] No operation", "INFO")
        else:
            self.log(f"Unknown action: {action}", "ERROR")
            return False

        if sound:
            self.log(f"[SOUND] Playing: {sound}", "INFO")
        return True

    async def handle_play(self, msg: dict):
        payload = msg.get("payload", {})
        self.log(f"[AUDIO] Playing: {payload.get('audio')}", "INFO")

    # --- State Machine Flow ---

    async def simulate_wake(self):
        self.set_state(State.WAKE)
        self.log("Wake word detected", "INFO")
        await asyncio.sleep(0.2)

    async def process_command(self, cmd_type: str, data):
        if cmd_type == "local":
            self.set_state(State.FORWARD_SERVER)
            await self.send_message(self.make_command_request(data))
        else:
            self.set_state(State.FORWARD_SERVER)
            await self.send_message(self.make_fallback_request(data))

        self.set_state(State.WAIT_ACTION)
        response = await self.receive_message()
        if not response: return

        msg_type = response.get("type", "")
        if msg_type == "action":
            self.set_state(State.LOCAL_EXECUTE)
            success = await self.handle_action(response)
            await self.send_message(self.make_action_result(success))
            self.set_state(State.PLAY_FEEDBACK)
            await asyncio.sleep(0.3)
        elif msg_type == "play":
            self.set_state(State.PLAY_FEEDBACK)
            await self.handle_play(response)
        
        self.set_state(State.IDLE)

    # --- Interactive CLI ---

    def print_help(self):
        print(f"\n{color('ESP32 Simulator Commands:', Colors.BOLD)}")
        print("  0-3: Local command, t <text>: Fallback, q: Quit, h: Help")

    async def interactive_loop(self):
        self.print_help()
        while self.running:
            try:
                def get_input():
                    try: return input(f"{Colors.GREEN}> {Colors.ENDC}")
                    except EOFError: return "q"
                
                cmd_line = await asyncio.get_event_loop().run_in_executor(None, get_input)
                cmd_line = cmd_line.strip()
                if not cmd_line or cmd_line == "q": self.running = False; break
                
                parts = cmd_line.split(" ", 1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                if cmd.isdigit():
                    await self.simulate_wake()
                    await self.process_command("local", int(cmd))
                elif cmd == "t":
                    await self.simulate_wake()
                    await self.process_command("fallback", args)
                elif cmd == "h": self.print_help()
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                self.set_state(State.IDLE)

    async def run(self):
        try:
            async with websockets.connect(self.ws_uri) as ws:
                self.ws = ws
                self.running = True
                self.reader_task = asyncio.create_task(self._reader_loop())
                self.log("Connected to server", "INFO")
                await self.interactive_loop()
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.running = False
            if self.reader_task: self.reader_task.cancel()
            print("Disconnected.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", default="esp32_01")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    sim = ESP32Simulator(SimulatorConfig(args.device_id, args.host, args.port))
    try: asyncio.run(sim.run())
    except KeyboardInterrupt: pass

if __name__ == "__main__":
    main()
