from .context import MetricsContext
from .aggregator import MetricsAggregator
from .logger import MetricsLogger

# Global singletons
aggregator = MetricsAggregator()
metrics_logger = MetricsLogger()

def init_metrics():
    """Start the metrics background writer."""
    metrics_logger.start()

def shutdown_metrics():
    """Stop the metrics background writer."""
    metrics_logger.stop()
