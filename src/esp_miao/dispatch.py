import httpx
import logging
from typing import Optional
from .connection import mqtt_client, device_table
from .config import MQTT_TOPIC
from .metrics import MetricsContext

logger = logging.getLogger("esp-miao.dispatch")

async def dispatch_command(target: str, value: str, metrics_ctx: Optional[MetricsContext] = None):
    """通用指令派發器，支援 MQTT 與 HTTP API。"""
    device = device_table.get_device(target)
    if not device:
        logger.warning(f"Attempted to control unregistered device: {target}")
        if metrics_ctx: metrics_ctx.set_error("unregistered_device")
        return

    # 決定發送方式：API 優先，MQTT 為輔
    if device.api_url:
        # HTTP API 模式 (針對 myxiaomi 等已有服務的專案)
        if metrics_ctx: metrics_ctx.mark_stage("dispatch_type", "http_api")
        
        cmd_payload = device.commands.get(value.lower(), value)
        logger.info(f"HTTP API Call: [{device.api_url}] -> cmd={cmd_payload} (for {target})")
        
        try:
            # 針對 myxiaomi (vacuumd) 的 CommandRequest 格式
            # device_id 在 myxiaomi 端固定為 robot_s5 (除非 Discovery 修改)
            payload = {
                "device_id": "robot_s5", 
                "command": cmd_payload
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(device.api_url, json=payload)
                if response.status_code == 200:
                    logger.info(f"HTTP Success: {response.json()}")
                    if metrics_ctx: metrics_ctx.set_flag("dispatch_success", True)
                else:
                    logger.error(f"HTTP Error {response.status_code}: {response.text}")
                    if metrics_ctx: metrics_ctx.set_error(f"http_error_{response.status_code}")
        except Exception as e:
            logger.error(f"HTTP Request failed for {target}: {e}")
            if metrics_ctx: metrics_ctx.set_error("http_exception")
    
    else:
        # MQTT 模式 (針對嵌入式裸機)
        if metrics_ctx: metrics_ctx.mark_stage("dispatch_type", "mqtt")
        
        topic = device.control_topic if device.control_topic else MQTT_TOPIC
        commands = device.commands if device.commands else {"on": "ON", "off": "OFF"}
        cmd_payload = commands.get(value.lower(), value.upper())

        try:
            result = mqtt_client.publish(topic, cmd_payload)
            if result.rc == 0:
                logger.info(f"MQTT Publish: [{topic}] -> {cmd_payload} (for {target})")
                if metrics_ctx: metrics_ctx.set_flag("dispatch_success", True)
            else:
                logger.error(f"Failed to publish MQTT command for {target} (rc={result.rc})")
                if metrics_ctx: metrics_ctx.set_error(f"mqtt_error_rc{result.rc}")
        except Exception as e:
            logger.error(f"MQTT Publish Error for {target}: {e}")
            if metrics_ctx: metrics_ctx.set_error("mqtt_exception")
