"""
Rate limiting for flight search requests.

This module provides a simple rate limiter to prevent overwhelming
Google Flights with too many requests.

Usage:
    >>> from fast_flights.rate_limit import get_rate_limiter
    >>> 
    >>> limiter = get_rate_limiter()
    >>> limiter.acquire()  # Blocks if rate limit exceeded
    >>> # ... make request ...
"""

from __future__ import annotations

import time
import threading
import logging
from collections import deque
from typing import Optional

from .config import get_config

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for controlling request frequency.
    
    Implements a sliding window rate limiter that tracks requests
    within a configurable time window.
    
    Thread-safe for concurrent usage.
    
    Attributes:
        max_requests: Maximum requests allowed per window
        window_seconds: Time window in seconds
        enabled: Whether rate limiting is active
    """
    
    def __init__(
        self,
        max_requests: Optional[int] = None,
        window_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum requests per window (default: from config)
            window_seconds: Time window in seconds (default: from config)
            enabled: Whether rate limiting is enabled (default: from config)
        """
        config = get_config()
        
        self.max_requests = max_requests if max_requests is not None else config.rate_limit_requests
        self.window_seconds = window_seconds if window_seconds is not None else config.rate_limit_window_seconds
        self.enabled = enabled if enabled is not None else config.rate_limit_enabled
        
        self._requests: deque[float] = deque()
        self._lock = threading.Lock()
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests outside the current window."""
        cutoff = time.time() - self.window_seconds
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Blocks until a request slot is available or timeout is reached.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
            
        Returns:
            True if acquired, False if timeout reached
            
        Example:
            >>> limiter = RateLimiter()
            >>> if limiter.acquire(timeout=5.0):
            ...     make_request()
            ... else:
            ...     print("Rate limit timeout")
        """
        if not self.enabled:
            return True
        
        start_time = time.time()
        
        while True:
            with self._lock:
                self._cleanup_old_requests()
                
                if len(self._requests) < self.max_requests:
                    self._requests.append(time.time())
                    return True
                
                # Calculate wait time
                oldest_request = self._requests[0]
                wait_time = oldest_request + self.window_seconds - time.time()
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(
                        f"Rate limit timeout after {elapsed:.2f}s "
                        f"({self.max_requests} requests per {self.window_seconds}s)"
                    )
                    return False
                # Adjust wait time for remaining timeout
                wait_time = min(wait_time, timeout - elapsed)
            
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                time.sleep(min(wait_time, 0.5))  # Check periodically
    
    def try_acquire(self) -> bool:
        """
        Try to acquire permission without blocking.
        
        Returns:
            True if acquired, False if rate limit would be exceeded
        """
        if not self.enabled:
            return True
        
        with self._lock:
            self._cleanup_old_requests()
            
            if len(self._requests) < self.max_requests:
                self._requests.append(time.time())
                return True
            
            return False
    
    def wait_time(self) -> float:
        """
        Get the time until a request slot is available.
        
        Returns:
            Seconds until next slot, or 0 if a slot is available
        """
        if not self.enabled:
            return 0.0
        
        with self._lock:
            self._cleanup_old_requests()
            
            if len(self._requests) < self.max_requests:
                return 0.0
            
            oldest_request = self._requests[0]
            return max(0.0, oldest_request + self.window_seconds - time.time())
    
    def remaining(self) -> int:
        """
        Get the number of remaining requests in the current window.
        
        Returns:
            Number of requests remaining
        """
        if not self.enabled:
            return self.max_requests
        
        with self._lock:
            self._cleanup_old_requests()
            return max(0, self.max_requests - len(self._requests))
    
    def reset(self) -> None:
        """Clear all tracked requests."""
        with self._lock:
            self._requests.clear()
    
    def __enter__(self) -> "RateLimiter":
        """Context manager that acquires on entry."""
        self.acquire()
        return self
    
    def __exit__(self, *args) -> None:
        """Context manager exit (no-op)."""
        pass


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.
    
    Creates a new instance on first call using configuration values.
    
    Returns:
        RateLimiter instance
        
    Example:
        >>> limiter = get_rate_limiter()
        >>> with limiter:
        ...     make_request()
    """
    global _rate_limiter
    
    if _rate_limiter is None:
        with _limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = RateLimiter()
    
    return _rate_limiter


def reset_rate_limiter() -> None:
    """
    Reset the global rate limiter.
    
    Clears tracked requests and recreates the limiter with current config.
    """
    global _rate_limiter
    
    with _limiter_lock:
        _rate_limiter = None


def rate_limited(func):
    """
    Decorator that applies rate limiting to a function.
    
    Example:
        >>> @rate_limited
        ... def fetch_flights():
        ...     # This function is now rate limited
        ...     pass
    """
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        limiter = get_rate_limiter()
        limiter.acquire()
        return func(*args, **kwargs)
    
    return wrapper


__all__ = [
    "RateLimiter",
    "get_rate_limiter",
    "reset_rate_limiter",
    "rate_limited",
]
