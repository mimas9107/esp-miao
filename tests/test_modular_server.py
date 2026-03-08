import pytest
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from esp_miao.connection import DynamicDeviceTable, device_table
from esp_miao.intent import extract_intent_from_text
from esp_miao.utils import get_action_sound
from esp_miao.models import Device
from esp_miao.dispatch import dispatch_command

# --- Test Connection Module (DynamicDeviceTable) ---

def test_device_table_aliases():
    """驗證別名對應是否正確。"""
    table = DynamicDeviceTable(devices=[
        Device(name="light", type="relay", aliases=["電燈", "燈泡"]),
        Device(name="vacuum", type="vacuum", aliases=["小貓", "機器人"])
    ])
    
    # 預設別名
    assert table.alias_map["燈"] == "light"
    assert table.alias_map["風扇"] == "fan" # 來自預設 defaults
    
    # 動態別名
    assert table.alias_map["電燈"] == "light"
    assert table.alias_map["小貓"] == "vacuum"
    assert table.alias_map["機器人"] == "vacuum"

def test_device_table_update():
    """驗證 MQTT Discovery 更新。"""
    table = DynamicDeviceTable(devices=[])
    dev_info = {
        "name": "heater",
        "type": "relay",
        "aliases": ["暖氣", "暖爐"],
        "control_topic": "home/heater/cmd"
    }
    table.update_device(dev_info)
    
    device = table.get_device("heater")
    assert device is not None
    assert device.type == "relay"
    assert "暖氣" in table.alias_map
    assert table.alias_map["暖氣"] == "heater"

# --- Test Intent Module ---

def test_extract_intent_keywords():
    """驗證關鍵字解析邏輯。"""
    # 測試開燈
    intent = extract_intent_from_text("幫我把燈打開")
    assert intent["action"] == "relay_set"
    assert intent["target"] == "light"
    assert intent["value"] == "on"
    
    # 測試掃地機器人特規 (只提名字預設為 on)
    intent = extract_intent_from_text("小貓過來")
    assert intent["target"] == "vacuum"
    assert intent["value"] == "on"
    
    # 測試未知指令
    intent = extract_intent_from_text("今天天氣如何")
    assert intent["action"] == "unknown"

# --- Test Utils Module ---

def test_action_sound_mapping():
    """驗證音效映射。"""
    assert get_action_sound("light", "on") == "lightopen.wav"
    assert get_action_sound("light", "off") == "lightclose.wav"
    assert get_action_sound("fan", "on") == "success.wav"
    assert get_action_sound("unknown", "any") == "success.wav"

# --- Test Dispatch Module (Mocked) ---

@pytest.mark.asyncio
async def test_dispatch_command_mqtt():
    """驗證 MQTT 派發。"""
    with patch("esp_miao.dispatch.mqtt_client") as mock_mqtt:
        mock_mqtt.publish.return_value.rc = 0
        
        # 測試燈光 (MQTT 模式)
        await dispatch_command("light", "on")
        
        # 驗證是否發送到正確的主題與內容
        # 註：light 在 connection.py 初始化為 "lamp/command"
        mock_mqtt.publish.assert_called_once()
        args, kwargs = mock_mqtt.publish.call_args
        assert args[0] == "lamp/command"
        assert args[1] == "ON"

@pytest.mark.asyncio
async def test_dispatch_command_http():
    """驗證 HTTP API 派發。"""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "ok"}
        
        # 測試掃地機器人 (HTTP API 模式)
        await dispatch_command("vacuum", "on")
        
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        json_data = mock_post.call_args[1]["json"]
        
        assert "192.168.1.16:8009" in url
        assert json_data["command"] == "start"
