#!/usr/bin/env python3
"""Test for ESP-MIAO Audio Request (ASR pipeline)."""

import asyncio
import base64
import json
import os
import sys
import time

try:
    import websockets
except ImportError:
    print("Error: websockets not installed")
    sys.exit(1)


async def test_audio_request():
    """Test audio_request communication with server."""
    uri = "ws://localhost:8000/ws/esp32_audio_test"
    device_id = "esp32_audio_test"

    print("=" * 60)
    print("ESP-MIAO Audio Request (ASR) Test")
    print("=" * 60)
    print()

    # Generate dummy PCM 16k 16bit mono data (3 seconds)
    # 16000 samples/sec * 3 sec * 2 bytes/sample = 96000 bytes
    sample_rate = 16000
    duration = 3
    data_size = sample_rate * duration * 2
    dummy_audio = b"\x00" * data_size

    audio_b64 = base64.b64encode(dummy_audio).decode("utf-8")

    try:
        async with websockets.connect(uri) as ws:
            print(f"[OK] Connected to {uri}")
            print()

            # Test: Audio Request
            print("-" * 40)
            print("Test: Audio Request (3s silent PCM)")
            print("-" * 40)

            msg = {
                "type": "audio_request",
                "device_id": device_id,
                "timestamp": int(time.time() * 1000),
                "payload": {
                    "audio_base64": audio_b64,
                    "audio_format": "pcm_16k_16bit",
                    "duration_ms": 3000,
                },
            }

            print(f"[SEND] audio_request (payload: {len(audio_b64)} bytes base64)")
            await ws.send(json.dumps(msg))

            # Wait for response (Whisper might take time)
            print("Waiting for ASR + LLM response...")
            response = await asyncio.wait_for(ws.recv(), timeout=60.0)
            print(f"[RECV] {response}")

            resp_data = json.loads(response)
            if resp_data.get("type") == "play":
                print("[OK] Received play response (likely 'not_understood.wav' because audio was silent)")
            elif resp_data.get("type") == "action":
                print("[OK] Received action response (Whisper somehow heard something?)")
            
            print()

            # Verify file was saved in src/esp_miao/audio/
            audio_dir = "src/esp_miao/audio"
            files = os.listdir(audio_dir)
            print(f"Files in {audio_dir}: {files}")
            if any(f"recorded_{device_id}" in f for f in files):
                print(f"[OK] Audio file was saved correctly.")
            else:
                print(f"[ERROR] Audio file was NOT found in {audio_dir}")

            print("=" * 60)
            print("Audio test completed!")
            print("=" * 60)

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_audio_request())
    sys.exit(0 if success else 1)
