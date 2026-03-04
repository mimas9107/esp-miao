import asyncio
import websockets
import json
import time

async def test_vacuum_command():
    uri = "ws://localhost:8000/ws/esp32_01"
    async with websockets.connect(uri) as websocket:
        # 模擬 ASR 辨識出的文字 "啟動掃地機器人"
        msg = {
            "device_id": "esp32_01",
            "timestamp": int(time.time() * 1000),
            "type": "fallback_request",
            "payload": {
                "text": "啟動掃地機器人"
            }
        }
        
        print(f"Sending: {msg['payload']['text']}")
        await websocket.send(json.dumps(msg))
        
        # 等待伺服器回應 (Action)
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            print(f"Server Response: {response}")
        except asyncio.TimeoutError:
            print("Timed out waiting for server response")

if __name__ == "__main__":
    asyncio.run(test_vacuum_command())
