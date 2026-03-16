import json
import re
import time
import logging
from typing import Optional
import ollama
from .connection import device_table
from .config import ACTION_KEYWORDS
from .metrics import MetricsContext

logger = logging.getLogger("esp-miao.intent")

def extract_intent_from_text(text: str) -> dict:
    """
    使用從 DeviceRegistry 獲取的動態別名地圖進行匹配，並優先使用裝置專屬關鍵字。
    """
    text_lower = text.replace(" ", "").lower()

    # 1. 找出目標裝置 (動態查詢 alias_map)
    target = None
    for alias, device_name in device_table.alias_map.items():
        if alias in text_lower:
            target = device_name
            break

    if not target:
        return {"action": "unknown", "target": "", "value": ""}

    # 2. 獲取該裝置的動作關鍵字 (有專屬用專屬，無則 fallback 全域)
    device_keywords = device_table.get_action_keywords(target)

    # 3. 找出動作
    value = None
    for action_value, keywords in device_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                value = action_value
                break
        if value:
            break

    if value:
        return {"action": "relay_set", "target": target, "value": value}
    
    # 原有的「掃地機預設啟動」邏輯已依計畫刪除，統一行為
    return {"action": "unknown", "target": target, "value": ""}


def parse_intent_with_llm(text: str, metrics_ctx: Optional[MetricsContext] = None) -> dict:
    """Use Ollama LLM to parse natural language intent with dynamic device list."""
    current_devices = [d.name for d in device_table.devices]

    # 先用關鍵字匹配提取意圖（作為驗證基準）
    keyword_intent = extract_intent_from_text(text)
    logger.debug(f"Keyword extraction: {text} -> {keyword_intent}")
    
    # 記錄關鍵字命中
    if metrics_ctx:
        metrics_ctx.set_flag("keyword_action_found", keyword_intent["action"] != "unknown")
        metrics_ctx.set_flag("keyword_target_found", keyword_intent["target"] != "")
    
    # --- 優先攔截邏輯 (Priority Logic) ---
    # 如果關鍵字已經能明確識別出目標與動作，直接返回，跳過 LLM 以降低延遲
    if keyword_intent["action"] != "unknown" and keyword_intent["target"] in current_devices:
        logger.info(f"Priority Logic: Keyword match successful for '{text}', skipping LLM.")
        if metrics_ctx: metrics_ctx.set_flag("llm_called", False)
        return keyword_intent

    # 如果內容完全沒提到裝置名稱且關鍵字解析失敗，不送 LLM，直接回傳 unknown
    if keyword_intent["target"] == "" and keyword_intent["action"] == "unknown":
        logger.info(f"Pre-filter: No devices found in '{text}', skipping LLM.")
        if metrics_ctx: metrics_ctx.set_flag("llm_called", False)
        return keyword_intent

    # 方案 B: 動態 LLM Prompt
    if metrics_ctx: metrics_ctx.set_flag("llm_called", True)
    
    prompt = f"""Task: Convert voice command to JSON.
Available devices: {current_devices}

Examples:
- Command: "幫我開燈" -> {{"action": "relay_set", "target": "light", "value": "on"}}
- Command: "關掉風扇" -> {{"action": "relay_set", "target": "fan", "value": "off"}}

Command: "{text}"
Response in ONE LINE JSON format ONLY:
"""

    try:
        t_llm = time.time()
        response = ollama.generate(model="qwen2.5:0.5b", prompt=prompt)
        if metrics_ctx: metrics_ctx.record_latency("llm_inference_latency", round(time.time() - t_llm, 3))
        
        result_text = response["response"]

        # Extract JSON from response
        json_match = re.search(r"\{[^}]+\}", result_text)
        if json_match:
            result_text = json_match.group()

        result = json.loads(result_text.strip())
        logger.info(f"LLM parsed: {text} -> {result}")

        # 驗證邏輯：如果 LLM 回報無效裝置，使用關鍵字結果
        if result.get("target") not in current_devices or result.get("value") not in ["on", "off"]:
            logger.warning(f"LLM output invalid device or value, falling back to keywords")
            return keyword_intent
            
        # 交叉驗證：以關鍵字匹配結果為準（如果存在）
        if keyword_intent["action"] != "unknown":
            if result.get("target") != keyword_intent["target"] or result.get("value") != keyword_intent["value"]:
                logger.warning(f"LLM disagreed with keywords, prioritizing keywords: {keyword_intent}")
                return keyword_intent

        if metrics_ctx: metrics_ctx.set_flag("llm_success", True)
        return result

    except Exception as e:
        logger.error(f"LLM parse error: {e}, using keyword result")
        return keyword_intent
