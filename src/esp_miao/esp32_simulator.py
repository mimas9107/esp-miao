#!/usr/bin/env python3
"""ESP32 Simulator for testing WebSocket communication.

This script simulates an ESP32 device connecting to the server,
implementing the state machine and protocol defined in SPEC.md.

Usage:
    uv run python -m esp_miao.esp32_simulator
    uv run python -m esp_miao.esp32_simulator --device-id esp32_test --host localhost --port 8000
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from enum import Enum

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

    async def receive_message(self) -> dict:
        """Receive JSON message from server."""
        if self.ws:
            raw = await self.ws.recv()
            self.log(f"<<< {raw}", "RECV")
            return json.loads(raw)
        return {}

    # --- Protocol Messages (from SPEC.md 1.2, 1.3) ---

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

    def make_action_result(self, success: bool, error: str = None) -> dict:
        """Create action_result message."""
        payload = {"status": "success" if success else "failure"}
        if error:
            payload["error"] = error
        return {
            "type": "action_result",
            "device_id": self.config.device_id,
            "timestamp": self.get_timestamp(),
            "payload": payload,
        }

    # --- Action Handlers ---

    async def handle_action(self, msg: dict) -> bool:
        """Handle action message from server. Returns success status."""
        payload = msg.get("payload", {})
        action = payload.get("action", "")
        target = payload.get("target", "")
        value = payload.get("value", "")
        sound = payload.get("sound", "")

        self.log(f"Executing: {action}({target}={value})", "INFO")

        # Simulate action execution
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
        """Handle play message from server."""
        payload = msg.get("payload", {})
        audio = payload.get("audio", "")
        self.log(f"[AUDIO] Playing: {audio}", "INFO")

    # --- State Machine Flow ---

    async def simulate_wake(self):
        """Simulate wake word detection."""
        self.set_state(State.WAKE)
        self.log("Wake word detected: 'Hi 喵喵'", "INFO")
        await asyncio.sleep(0.5)

    async def simulate_listen(self):
        """Simulate listening for command."""
        self.set_state(State.LISTEN)
        self.log("Listening for command...", "INFO")
        await asyncio.sleep(1.0)

    async def simulate_recognize(self, cmd_id: int = None, text: str = None):
        """Simulate esp-sr recognition."""
        self.set_state(State.RECOGNIZE)

        if cmd_id is not None and cmd_id in COMMANDS:
            # Local command matched
            cmd_name, target, value = COMMANDS[cmd_id]
            self.log(f"Recognized local command: {cmd_name} (id={cmd_id})", "INFO")
            return ("local", cmd_id)
        else:
            # Fallback to server
            self.log(f"No local match, fallback: '{text}'", "INFO")
            return ("fallback", text)

    async def process_command(self, cmd_type: str, data):
        """Process recognized command through state machine."""
        if cmd_type == "local":
            # Send to server for confirmation/action
            self.set_state(State.FORWARD_SERVER)
            await self.send_message(self.make_command_request(data))
        else:
            # Fallback request
            self.set_state(State.FORWARD_SERVER)
            await self.send_message(self.make_fallback_request(data))

        # Wait for server response
        self.set_state(State.WAIT_ACTION)
        response = await self.receive_message()

        msg_type = response.get("type", "")

        if msg_type == "action":
            self.set_state(State.LOCAL_EXECUTE)
            success = await self.handle_action(response)

            # Send result back
            await self.send_message(self.make_action_result(success))

            # Play feedback
            self.set_state(State.PLAY_FEEDBACK)
            await asyncio.sleep(0.3)

        elif msg_type == "play":
            self.set_state(State.PLAY_FEEDBACK)
            await self.handle_play(response)

        else:
            self.set_state(State.ERROR)
            self.log(f"Unexpected response type: {msg_type}", "ERROR")

        # Return to idle
        self.set_state(State.IDLE)

    # --- Interactive CLI ---

    def print_help(self):
        print(
            f"""
{color("ESP32 Simulator Commands:", Colors.BOLD)}

  {color("0-3", Colors.GREEN)}      Send local command (0=LIGHT_ON, 1=LIGHT_OFF, 2=FAN_ON, 3=FAN_OFF)
  {color("t <text>", Colors.GREEN)} Send fallback text request (e.g., 't 開燈')
  {color("w", Colors.GREEN)}        Simulate full wake->listen->recognize flow
  {color("s", Colors.GREEN)}        Show current state
  {color("h", Colors.GREEN)}        Show this help
  {color("q", Colors.GREEN)}        Quit

{color("Example:", Colors.DIM)}
  > 0          # Send LIGHT_ON command
  > t 打開電風扇  # Send fallback text
  > w          # Simulate wake word flow
"""
        )

    async def interactive_loop(self):
        """Run interactive command loop."""
        self.print_help()

        while self.running:
            try:
                # Use asyncio for non-blocking input
                cmd = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input(f"{Colors.GREEN}> {Colors.ENDC}")
                )
                cmd = cmd.strip()

                if not cmd:
                    continue

                if cmd == "q":
                    self.running = False
                    break

                elif cmd == "h":
                    self.print_help()

                elif cmd == "s":
                    self.log(f"Current state: {self.state.value}", "INFO")

                elif cmd == "w":
                    # Full wake flow simulation
                    await self.simulate_wake()
                    await self.simulate_listen()
                    # Ask for command
                    user_cmd = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: input(
                            f"{Colors.CYAN}Enter command (0-3 or text): {Colors.ENDC}"
                        ),
                    )
                    user_cmd = user_cmd.strip()

                    if user_cmd.isdigit():
                        cmd_id = int(user_cmd)
                        result = await self.simulate_recognize(cmd_id=cmd_id)
                    else:
                        result = await self.simulate_recognize(text=user_cmd)

                    await self.process_command(*result)

                elif cmd.isdigit():
                    # Direct command send
                    cmd_id = int(cmd)
                    if cmd_id in COMMANDS:
                        await self.simulate_wake()
                        result = await self.simulate_recognize(cmd_id=cmd_id)
                        await self.process_command(*result)
                    else:
                        self.log(f"Unknown command ID: {cmd_id}", "ERROR")

                elif cmd.startswith("t "):
                    # Fallback text
                    text = cmd[2:].strip()
                    if text:
                        await self.simulate_wake()
                        result = await self.simulate_recognize(text=text)
                        await self.process_command(*result)
                    else:
                        self.log("Please provide text after 't'", "ERROR")

                else:
                    self.log(f"Unknown command: {cmd}. Type 'h' for help.", "ERROR")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                self.set_state(State.ERROR)
                await asyncio.sleep(1)
                self.set_state(State.IDLE)

    async def run(self):
        """Main run loop."""
        print(
            f"""
{color("=" * 60, Colors.BOLD)}
{color("ESP32 Simulator", Colors.BOLD)} - {color(self.config.device_id, Colors.CYAN)}
{color("=" * 60, Colors.BOLD)}

Connecting to: {color(self.ws_uri, Colors.BLUE)}
"""
        )

        try:
            async with websockets.connect(self.ws_uri) as ws:
                self.ws = ws
                self.running = True
                self.log(f"Connected to server", "INFO")
                self.set_state(State.IDLE)

                await self.interactive_loop()

        except ConnectionRefusedError:
            print(f"\n{color('Error:', Colors.RED)} Could not connect to {self.ws_uri}")
            print(
                f"Make sure the server is running: {color('uv run esp-miao', Colors.GREEN)}"
            )
            sys.exit(1)
        except Exception as e:
            print(f"\n{color('Error:', Colors.RED)} {e}")
            sys.exit(1)
        finally:
            self.ws = None
            print(f"\n{color('Disconnected.', Colors.DIM)}")


def main():
    parser = argparse.ArgumentParser(
        description="ESP32 Simulator for testing WebSocket communication"
    )
    parser.add_argument(
        "--device-id",
        default="esp32_01",
        help="Device ID (default: esp32_01)",
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="Server host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000)",
    )

    args = parser.parse_args()

    config = SimulatorConfig(
        device_id=args.device_id,
        host=args.host,
        port=args.port,
    )

    simulator = ESP32Simulator(config)

    try:
        asyncio.run(simulator.run())
    except KeyboardInterrupt:
        print(f"\n{color('Interrupted.', Colors.DIM)}")


if __name__ == "__main__":
    main()
