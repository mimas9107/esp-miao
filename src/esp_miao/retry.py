"""Retry utilities for ESP-MIAO.

Provides retry logic for unreliable operations like network calls.
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger("esp-miao.retry")

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt (0-indexed)."""
        delay = self.base_delay * (self.exponential_base**attempt)
        return min(delay, self.max_delay)


# Default retry config
DEFAULT_RETRY = RetryConfig(max_attempts=3, base_delay=0.5, max_delay=5.0)


async def retry_async(
    func: Callable[..., T],
    *args,
    config: RetryConfig = DEFAULT_RETRY,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        config: Retry configuration
        exceptions: Tuple of exception types to catch and retry
        **kwargs: Keyword arguments for func

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = config.get_delay(attempt)
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_attempts} attempts failed. Last error: {e}"
                )

    raise last_exception


def with_retry(
    config: RetryConfig = DEFAULT_RETRY,
    exceptions: tuple = (Exception,),
):
    """
    Decorator for async functions to add retry logic.

    Usage:
        @with_retry(config=RetryConfig(max_attempts=5))
        async def my_unreliable_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                func, *args, config=config, exceptions=exceptions, **kwargs
            )

        return wrapper

    return decorator


class RetryableWebSocket:
    """WebSocket wrapper with automatic reconnection."""

    def __init__(
        self,
        uri: str,
        config: RetryConfig = DEFAULT_RETRY,
    ):
        self.uri = uri
        self.config = config
        self.ws = None

    async def connect(self):
        """Connect with retry."""
        import websockets

        async def _connect():
            self.ws = await websockets.connect(self.uri)
            return self.ws

        return await retry_async(
            _connect,
            config=self.config,
            exceptions=(ConnectionError, OSError),
        )

    async def send(self, message: str):
        """Send with automatic reconnection on failure."""
        if self.ws is None:
            await self.connect()

        try:
            await self.ws.send(message)
        except Exception:
            await self.connect()
            await self.ws.send(message)

    async def recv(self) -> str:
        """Receive message."""
        if self.ws is None:
            await self.connect()
        return await self.ws.recv()

    async def close(self):
        """Close connection."""
        if self.ws:
            await self.ws.close()
            self.ws = None
