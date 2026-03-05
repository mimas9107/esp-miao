import json
import threading
import queue
import time
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("esp-miao.metrics")

class MetricsLogger:
    """
    Async JSONL writer using a background thread and queue.
    Ensures main loop is never blocked by file I/O.
    """
    def __init__(self, log_path: str = "metrics.jsonl", flush_interval: int = 2):
        self.log_path = Path(log_path)
        self.queue: queue.Queue = queue.Queue()
        self.flush_interval = flush_interval
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._writer_loop, name="MetricsWriter", daemon=True)
        self._lock = threading.Lock() # Just in case
        
    def start(self):
        """Start the background writer thread."""
        if not self._thread.is_alive():
            self._stop_event.clear()
            self._thread.start()
            logger.info(f"Metrics logger started. Writing to {self.log_path}")

    def stop(self):
        """Stop the writer thread gracefully."""
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Metrics logger stopped.")

    def log(self, data: Dict[str, Any]):
        """Queue a metrics record for writing."""
        self.queue.put(data)

    def _writer_loop(self):
        """Background loop to flush queue to disk."""
        buffer = []
        last_flush = time.time()

        while not self._stop_event.is_set() or not self.queue.empty():
            try:
                # Wait for item with timeout to allow periodic flush checking
                try:
                    item = self.queue.get(timeout=0.5)
                    buffer.append(item)
                except queue.Empty:
                    pass

                now = time.time()
                if buffer and (now - last_flush > self.flush_interval or len(buffer) > 10):
                    self._flush_buffer(buffer)
                    buffer = [] # Create new list
                    last_flush = now
                    
            except Exception as e:
                logger.error(f"Error in metrics writer loop: {e}")
                time.sleep(1) # Prevent busy loop on error

        # Final flush
        if buffer:
            self._flush_buffer(buffer)

    def _flush_buffer(self, buffer: list):
        """Write buffer to file."""
        if not buffer:
            return
            
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                for item in buffer:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write metrics to disk: {e}")
