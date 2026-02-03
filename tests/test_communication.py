#!/usr/bin/env python3
"""Non-interactive test for ESP32 simulator and server communication."""

import asyncio
import json
import sys
import time

try:
    import websockets
except ImportError:
    print("Error: websockets not installed")
    sys.exit(1)


async def test_communication():
    """Test WebSocket communication with server."""
    uri = "ws://localhost:8000/ws/esp32_test"
    device_id = "esp32_test"

    print("=" * 60)
    print("ESP-MIAO Communication Test")
    print("=" * 60)
    print()

    try:
        async with websockets.connect(uri) as ws:
            print(f"[OK] Connected to {uri}")
            print()

            # Test 1: Command Request (LIGHT_ON)
            print("-" * 40)
            print("Test 1: Command Request (LIGHT_ON, cmd_id=0)")
            print("-" * 40)

            msg1 = {
                "type": "command_request",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {
                    "source": "esp-sr",
                    "cmd_id": 0,
                    "cmd_name": "LIGHT_ON",
                    "confidence": 0.95,
                },
            }

            print(f"[SEND] {json.dumps(msg1, ensure_ascii=False)}")
            await ws.send(json.dumps(msg1))

            response1 = await ws.recv()
            print(f"[RECV] {response1}")

            resp1_data = json.loads(response1)
            if resp1_data.get("type") == "action":
                print("[OK] Received action response")
            else:
                print(f"[WARN] Unexpected response type: {resp1_data.get('type')}")

            print()

            # Test 2: Command Request (LIGHT_OFF)
            print("-" * 40)
            print("Test 2: Command Request (LIGHT_OFF, cmd_id=1)")
            print("-" * 40)

            msg2 = {
                "type": "command_request",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {
                    "source": "esp-sr",
                    "cmd_id": 1,
                    "cmd_name": "LIGHT_OFF",
                    "confidence": 0.92,
                },
            }

            print(f"[SEND] {json.dumps(msg2, ensure_ascii=False)}")
            await ws.send(json.dumps(msg2))

            response2 = await ws.recv()
            print(f"[RECV] {response2}")
            print()

            # Test 3: Fallback Request
            print("-" * 40)
            print("Test 3: Fallback Request (text)")
            print("-" * 40)

            msg3 = {
                "type": "fallback_request",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {"text": "打開電風扇"},
            }

            print(f"[SEND] {json.dumps(msg3, ensure_ascii=False)}")
            await ws.send(json.dumps(msg3))

            response3 = await asyncio.wait_for(ws.recv(), timeout=30.0)
            print(f"[RECV] {response3}")
            print()

            # Test 4: Action Result
            print("-" * 40)
            print("Test 4: Action Result (success)")
            print("-" * 40)

            msg4 = {
                "type": "action_result",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {"status": "success"},
            }

            print(f"[SEND] {json.dumps(msg4, ensure_ascii=False)}")
            await ws.send(json.dumps(msg4))
            print("[OK] Action result sent (no response expected)")
            print()

            # Test 5: Unknown command
            print("-" * 40)
            print("Test 5: Unknown Command (cmd_id=99)")
            print("-" * 40)

            msg5 = {
                "type": "command_request",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {
                    "source": "esp-sr",
                    "cmd_id": 99,
                    "cmd_name": "UNKNOWN",
                    "confidence": 0.5,
                },
            }

            print(f"[SEND] {json.dumps(msg5, ensure_ascii=False)}")
            await ws.send(json.dumps(msg5))

            response5 = await ws.recv()
            print(f"[RECV] {response5}")

            resp5_data = json.loads(response5)
            if resp5_data.get("type") == "play":
                print("[OK] Received play (error sound) response for unknown command")
            print()

            print("=" * 60)
            print("All tests completed!")
            print("=" * 60)

    except ConnectionRefusedError:
        print(f"[ERROR] Could not connect to {uri}")
        print("Make sure the server is running: uv run esp-miao")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_communication())
    sys.exit(0 if success else 1)
