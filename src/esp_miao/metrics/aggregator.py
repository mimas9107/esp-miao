import threading
from typing import Dict
from .context import MetricsContext

class MetricsAggregator:
    """
    In-memory aggregator for global statistics.
    Thread-safe counter management.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.stats = {
            "total_requests": 0,
            "llm_calls": 0,
            "llm_success": 0,
            "keyword_success": 0,
            "total_latency_sum": 0.0,
            "asr_latency_sum": 0.0,
            "errors": 0
        }

    def record(self, context: MetricsContext):
        """Update global stats from a finalized context."""
        data = context.data
        with self._lock:
            self.stats["total_requests"] += 1
            if data.get("llm_called"):
                self.stats["llm_calls"] += 1
                if data.get("llm_success"):
                    self.stats["llm_success"] += 1
            
            if data.get("keyword_action_found"):
                self.stats["keyword_success"] += 1
                
            self.stats["total_latency_sum"] += data.get("total_latency", 0.0)
            self.stats["asr_latency_sum"] += data.get("asr_latency", 0.0)
            
            if data.get("error_type"):
                self.stats["errors"] += 1

    def snapshot(self) -> Dict[str, float]:
        """Return a snapshot of current stats."""
        with self._lock:
            s = self.stats.copy()
            
        count = s["total_requests"]
        return {
            "requests": count,
            "llm_ratio": round(s["llm_calls"] / count if count else 0, 2),
            "avg_latency": round(s["total_latency_sum"] / count if count else 0, 3),
            "avg_asr": round(s["asr_latency_sum"] / count if count else 0, 3),
            "error_rate": round(s["errors"] / count if count else 0, 2)
        }
