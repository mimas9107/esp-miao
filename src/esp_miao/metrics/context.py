import time
from typing import Any, Dict, Optional

class MetricsContext:
    """
    Context object for tracking metrics of a single request.
    Designed to be lightweight and passed through the request lifecycle.
    """
    def __init__(self, request_id: str, device_id: str):
        self.request_id = request_id
        self.device_id = device_id
        self.start_time = time.time()
        self.data: Dict[str, Any] = {
            "request_id": request_id,
            "device_id": device_id,
            "timestamp": int(self.start_time),
            # Default values
            "asr_latency": 0.0,
            "asr_text_length": 0,
            "asr_empty": False,
            "keyword_action_found": False,
            "keyword_target_found": False,
            "llm_called": False,
            "llm_latency": 0.0,
            "llm_success": False,
            "validator_pass": False,
            "reject_reason": None,
            "dispatch_type": None,
            "dispatch_success": False,
            "error_type": None,
            "total_latency": 0.0
        }

    def mark_stage(self, name: str, value: Any):
        """Record a generic stage value."""
        self.data[name] = value

    def set_flag(self, key: str, value: bool):
        """Set a boolean flag."""
        self.data[key] = value

    def record_latency(self, key: str, seconds: float):
        """Record a latency measurement."""
        self.data[key] = seconds

    def set_error(self, error: str):
        """Record an error type."""
        self.data["error_type"] = str(error)

    def finalize(self) -> Dict[str, Any]:
        """
        Finalize the context, calculate total latency, and return the data dict.
        Should be called at the end of the request processing.
        """
        end_time = time.time()
        self.data["total_latency"] = round(end_time - self.start_time, 3)
        
        # Ensure timestamp is integer for JSON compatibility
        if "timestamp" in self.data and isinstance(self.data["timestamp"], float):
             self.data["timestamp"] = int(self.data["timestamp"])
             
        return self.data
