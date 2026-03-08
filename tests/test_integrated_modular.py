import pytest
import json
import base64
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from esp_miao.app import app

client = TestClient(app)

# --- Test FastAPI Endpoints ---

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_list_devices():
    response = client.get("/devices")
    assert response.status_code == 200
    devices = response.json()
    assert any(d["name"] == "light" for d in devices)

# --- Test WebSocket Communication (Mocking ASR/LLM) ---

@pytest.mark.asyncio
async def test_websocket_audio_request():
    """模擬完整的 WebSocket audio_request 流程。"""
    
    # 模擬轉錄與意圖解析，避免啟動重型模型
    with patch("esp_miao.app.transcribe_audio", new_callable=AsyncMock) as mock_asr, \
         patch("esp_miao.app.parse_intent_with_llm") as mock_llm, \
         patch("esp_miao.app.dispatch_command", new_callable=AsyncMock) as mock_dispatch, \
         patch("esp_miao.app.play_local_sound", new_callable=AsyncMock):
        
        mock_asr.return_value = "把燈打開"
        mock_llm.return_value = {"action": "relay_set", "target": "light", "value": "on"}
        
        with client.websocket_connect("/ws/test_device") as websocket:
            # 1. 接收連線後的 TimeSync
            sync_data = websocket.receive_json()
            assert sync_data["type"] == "time_sync"
            
            # 2. 發送 Audio Request
            audio_data = base64.b64encode(b"fake_pcm_data").decode("utf-8")
            websocket.send_json({
                "type": "audio_request",
                "device_id": "test_device",
                "timestamp": 123456789,
                "payload": {
                    "audio_base64": audio_data,
                    "audio_format": "pcm_16k_16bit",
                    "duration_ms": 1000
                }
            })
            
            # 3. 接收 Action 響應
            action_data = websocket.receive_json()
            assert action_data["type"] == "action"
            assert action_data["payload"]["target"] == "light"
            assert action_data["payload"]["value"] == "on"
            
            # 驗證 ASR 與 LLM 是否被正確呼叫
            mock_asr.assert_called_once()
            mock_llm.assert_called_once()
            mock_dispatch.assert_called_once_with("light", "on", ANY)

@pytest.mark.asyncio
async def test_websocket_command_request():
    """模擬 local command_request 流程。"""
    with patch("esp_miao.app.dispatch_command", new_callable=AsyncMock) as mock_dispatch, \
         patch("esp_miao.app.play_local_sound", new_callable=AsyncMock):
        
        with client.websocket_connect("/ws/test_device") as websocket:
            # 忽略 TimeSync
            websocket.receive_json()
            
            # 發送 Command Request (ID 0 = LIGHT_ON)
            websocket.send_json({
                "type": "command_request",
                "device_id": "test_device",
                "timestamp": 123456789,
                "payload": {
                    "source": "esp-sr",
                    "cmd_id": 0,
                    "cmd_name": "LIGHT_ON",
                    "confidence": 0.99
                }
            })
            
            # 接收 Action 響應
            action_data = websocket.receive_json()
            assert action_data["type"] == "action"
            assert action_data["payload"]["target"] == "light"
            assert action_data["payload"]["value"] == "on"
            
            mock_dispatch.assert_called_once_with("light", "on")
