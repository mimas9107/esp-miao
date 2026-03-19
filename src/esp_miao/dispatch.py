import logging
from typing import Optional
from .connection import mqtt_client, device_table
from .config import MQTT_TOPIC
from .metrics import MetricsContext

logger = logging.getLogger("esp-miao.dispatch")

async def dispatch_command(target: str, value: str, metrics_ctx: Optional[MetricsContext] = None):
    """通用指令派發器，全面採用 MQTT 模式。"""
    device = device_table.get_device(target)
    if not device:
        logger.warning(f"Attempted to control unregistered device: {target}")
        if metrics_ctx: metrics_ctx.set_error("unregistered_device")
        return

    # MQTT 模式
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
