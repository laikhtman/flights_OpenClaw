"""
Retry logic with exponential backoff for flight searches.

This module provides decorators and utilities for retrying failed requests
with configurable backoff strategies.

Usage:
    >>> from fast_flights.retry import retry_with_backoff
    >>> 
    >>> @retry_with_backoff(max_retries=3)
    >>> def my_function():
    ...     # May raise retryable exceptions
    ...     pass
"""

from __future__ import annotations

import time
import random
import logging
from functools import wraps
from typing import Callable, TypeVar, Tuple, Type, Optional, Any

from .config import get_config

logger = logging.getLogger(__name__)

# Type variables for generic decorator
F = TypeVar('F', bound=Callable[..., Any])


# Default exceptions that should trigger a retry
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    AssertionError,  # HTTP errors (status code assertions)
    RuntimeError,    # Parsing errors
    ConnectionError, # Network errors
    TimeoutError,    # Timeout errors
)


def retry_with_backoff(
    max_retries: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    exponential_base: Optional[float] = None,
    jitter: Optional[bool] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
) -> Callable[[F], F]:
    """
    Decorator that retries a function with exponential backoff.
    
    Useful for handling transient failures when scraping Google Flights.
    Uses configuration from get_config() for default values.
    
    Args:
        max_retries: Maximum number of retry attempts (default: from config)
        base_delay: Base delay between retries in seconds (default: from config)
        max_delay: Maximum delay between retries in seconds (default: from config)
        exponential_base: Base for exponential backoff (default: from config)
        jitter: Add random jitter to delays (default: from config)
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called before each retry with
                  (exception, attempt_number, delay)
    
    Returns:
        Decorated function that will retry on specified exceptions
        
    Example:
        >>> @retry_with_backoff(max_retries=3)
        ... def fetch_flights():
        ...     # May raise exceptions
        ...     pass
        
        >>> @retry_with_backoff(
        ...     max_retries=5,
        ...     base_delay=2.0,
        ...     retryable_exceptions=(ConnectionError, TimeoutError)
        ... )
        ... def custom_fetch():
        ...     pass
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get config defaults
            config = get_config()
            
            # Use provided values or fall back to config
            _max_retries = max_retries if max_retries is not None else config.max_retries
            _base_delay = base_delay if base_delay is not None else config.retry_base_delay
            _max_delay = max_delay if max_delay is not None else config.retry_max_delay
            _exp_base = exponential_base if exponential_base is not None else config.retry_exponential_base
            _jitter = jitter if jitter is not None else config.retry_jitter
            _exceptions = retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS
            
            last_exception: Optional[Exception] = None
            
            for attempt in range(_max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except _exceptions as e:
                    last_exception = e
                    
                    # Don't retry on the last attempt
                    if attempt >= _max_retries:
                        logger.warning(
                            f"All {_max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        _base_delay * (_exp_base ** attempt),
                        _max_delay
                    )
                    
                    # Add jitter if enabled (±50%)
                    if _jitter:
                        delay *= (0.5 + random.random())
                    
                    logger.info(
                        f"Attempt {attempt + 1}/{_max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1, delay)
                    
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")
        
        return wrapper  # type: ignore
    
    return decorator


class RetryContext:
    """
    Context manager for retry logic with backoff.
    
    Useful when you need more control over the retry loop.
    
    Example:
        >>> with RetryContext(max_retries=3) as retry:
        ...     for attempt in retry:
        ...         try:
        ...             result = do_something()
        ...             break  # Success, exit loop
        ...         except Exception as e:
        ...             retry.record_failure(e)
    """
    
    def __init__(
        self,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        exponential_base: Optional[float] = None,
        jitter: Optional[bool] = None,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        config = get_config()
        
        self.max_retries = max_retries if max_retries is not None else config.max_retries
        self.base_delay = base_delay if base_delay is not None else config.retry_base_delay
        self.max_delay = max_delay if max_delay is not None else config.retry_max_delay
        self.exponential_base = exponential_base if exponential_base is not None else config.retry_exponential_base
        self.jitter = jitter if jitter is not None else config.retry_jitter
        self.retryable_exceptions = retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS
        
        self._attempt = 0
        self._last_exception: Optional[Exception] = None
        self._should_continue = True
    
    def __enter__(self) -> "RetryContext":
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        # Don't suppress exceptions
        return False
    
    def __iter__(self) -> "RetryContext":
        self._attempt = 0
        self._should_continue = True
        return self
    
    def __next__(self) -> int:
        if not self._should_continue:
            raise StopIteration
        
        if self._attempt > self.max_retries:
            if self._last_exception:
                raise self._last_exception
            raise StopIteration
        
        current_attempt = self._attempt
        self._attempt += 1
        return current_attempt
    
    def record_failure(self, exception: Exception) -> None:
        """
        Record a failure and sleep before the next retry.
        
        Args:
            exception: The exception that caused the failure
        """
        self._last_exception = exception
        
        # Check if this is a retryable exception
        if not isinstance(exception, self.retryable_exceptions):
            self._should_continue = False
            raise exception
        
        # Check if we've exhausted retries
        if self._attempt > self.max_retries:
            self._should_continue = False
            return
        
        # Calculate delay
        delay = min(
            self.base_delay * (self.exponential_base ** (self._attempt - 1)),
            self.max_delay
        )
        
        if self.jitter:
            delay *= (0.5 + random.random())
        
        logger.info(
            f"Attempt {self._attempt}/{self.max_retries + 1} failed: {exception}. "
            f"Retrying in {delay:.2f}s..."
        )
        
        time.sleep(delay)
    
    def success(self) -> None:
        """Mark the current attempt as successful and stop retrying."""
        self._should_continue = False


def is_retryable_error(exception: Exception) -> bool:
    """
    Check if an exception should trigger a retry.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception is retryable
    """
    error_str = str(exception).lower()
    
    # Rate limiting
    if "429" in error_str or "rate" in error_str or "too many" in error_str:
        return True
    
    # Temporary server errors
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True
    
    # Network errors
    if any(x in error_str for x in ["connection", "timeout", "network", "dns"]):
        return True
    
    # Check exception type
    return isinstance(exception, DEFAULT_RETRYABLE_EXCEPTIONS)


__all__ = [
    "retry_with_backoff",
    "RetryContext",
    "is_retryable_error",
    "DEFAULT_RETRYABLE_EXCEPTIONS",
]
