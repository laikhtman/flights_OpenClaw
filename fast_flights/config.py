"""
Configuration management for fast-flights.

This module provides centralized configuration for the library,
supporting environment variables, .env files, and programmatic configuration.

Usage:
    >>> from fast_flights.config import get_config, configure
    >>> 
    >>> # Get current config
    >>> config = get_config()
    >>> print(config.default_fetch_mode)
    
    >>> # Update config programmatically
    >>> configure(max_retries=5, default_fetch_mode="fallback")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Optional

# Try to use pydantic-settings for advanced config
try:
    from pydantic_settings import BaseSettings
    from pydantic import Field as PydanticField
    PYDANTIC_SETTINGS_AVAILABLE = True
except ImportError:
    PYDANTIC_SETTINGS_AVAILABLE = False


FetchMode = Literal["common", "fallback", "force-fallback", "local", "bright-data"]


if PYDANTIC_SETTINGS_AVAILABLE:
    class FlightConfig(BaseSettings):
        """
        Configuration for fast-flights.
        
        Settings can be provided via:
        1. Environment variables (prefixed with FAST_FLIGHTS_)
        2. .env file
        3. Direct instantiation
        
        Example:
            Set via environment:
            $ export FAST_FLIGHTS_DEFAULT_FETCH_MODE=fallback
            $ export FAST_FLIGHTS_MAX_RETRIES=5
            
            Or in code:
            >>> from fast_flights.config import configure
            >>> configure(max_retries=5)
        """
        
        # Fetch settings
        default_fetch_mode: FetchMode = PydanticField(
            default="fallback",
            description="Default HTTP fetch strategy"
        )
        data_source: Literal["html", "js"] = PydanticField(
            default="html",
            description="Default data source for parsing"
        )
        
        # Retry settings
        max_retries: int = PydanticField(
            default=3,
            ge=0,
            le=10,
            description="Maximum number of retry attempts"
        )
        retry_base_delay: float = PydanticField(
            default=1.0,
            ge=0.1,
            le=30.0,
            description="Base delay between retries in seconds"
        )
        retry_max_delay: float = PydanticField(
            default=30.0,
            ge=1.0,
            le=300.0,
            description="Maximum delay between retries in seconds"
        )
        retry_exponential_base: float = PydanticField(
            default=2.0,
            ge=1.5,
            le=4.0,
            description="Exponential base for backoff calculation"
        )
        retry_jitter: bool = PydanticField(
            default=True,
            description="Add random jitter to retry delays"
        )
        
        # Rate limiting
        rate_limit_enabled: bool = PydanticField(
            default=True,
            description="Enable rate limiting"
        )
        rate_limit_requests: int = PydanticField(
            default=30,
            ge=1,
            le=1000,
            description="Maximum requests per time window"
        )
        rate_limit_window_seconds: int = PydanticField(
            default=60,
            ge=1,
            le=3600,
            description="Rate limit time window in seconds"
        )
        
        # Bright Data settings
        bright_data_api_key: Optional[str] = PydanticField(
            default=None,
            description="Bright Data API key for SERP API"
        )
        bright_data_api_url: str = PydanticField(
            default="https://api.brightdata.com/request",
            description="Bright Data API URL"
        )
        
        # Logging
        log_level: str = PydanticField(
            default="INFO",
            description="Logging level"
        )
        
        # Cookie consent
        cookie_consent: bool = PydanticField(
            default=True,
            description="Use embedded consent cookies if no cookies provided"
        )
        
        model_config = {
            "env_prefix": "FAST_FLIGHTS_",
            "env_file": ".env",
            "env_file_encoding": "utf-8",
            "extra": "ignore",
        }

else:
    # Fallback dataclass-based config when pydantic-settings not available
    @dataclass
    class FlightConfig:
        """
        Configuration for fast-flights (dataclass fallback).
        
        Settings can be set via environment variables prefixed with FAST_FLIGHTS_.
        """
        
        # Fetch settings
        default_fetch_mode: FetchMode = "fallback"
        data_source: Literal["html", "js"] = "html"
        
        # Retry settings
        max_retries: int = 3
        retry_base_delay: float = 1.0
        retry_max_delay: float = 30.0
        retry_exponential_base: float = 2.0
        retry_jitter: bool = True
        
        # Rate limiting
        rate_limit_enabled: bool = True
        rate_limit_requests: int = 30
        rate_limit_window_seconds: int = 60
        
        # Bright Data settings
        bright_data_api_key: Optional[str] = None
        bright_data_api_url: str = "https://api.brightdata.com/request"
        
        # Logging
        log_level: str = "INFO"
        
        # Cookie consent
        cookie_consent: bool = True
        
        @classmethod
        def from_env(cls) -> "FlightConfig":
            """Create config from environment variables."""
            def get_env(key: str, default: str) -> str:
                return os.environ.get(f"FAST_FLIGHTS_{key}", default)
            
            def get_env_bool(key: str, default: bool) -> bool:
                val = get_env(key, str(default)).lower()
                return val in ("true", "1", "yes")
            
            def get_env_int(key: str, default: int) -> int:
                try:
                    return int(get_env(key, str(default)))
                except ValueError:
                    return default
            
            def get_env_float(key: str, default: float) -> float:
                try:
                    return float(get_env(key, str(default)))
                except ValueError:
                    return default
            
            return cls(
                default_fetch_mode=get_env("DEFAULT_FETCH_MODE", "fallback"),  # type: ignore
                data_source=get_env("DATA_SOURCE", "html"),  # type: ignore
                max_retries=get_env_int("MAX_RETRIES", 3),
                retry_base_delay=get_env_float("RETRY_BASE_DELAY", 1.0),
                retry_max_delay=get_env_float("RETRY_MAX_DELAY", 30.0),
                retry_exponential_base=get_env_float("RETRY_EXPONENTIAL_BASE", 2.0),
                retry_jitter=get_env_bool("RETRY_JITTER", True),
                rate_limit_enabled=get_env_bool("RATE_LIMIT_ENABLED", True),
                rate_limit_requests=get_env_int("RATE_LIMIT_REQUESTS", 30),
                rate_limit_window_seconds=get_env_int("RATE_LIMIT_WINDOW_SECONDS", 60),
                bright_data_api_key=os.environ.get("FAST_FLIGHTS_BRIGHT_DATA_API_KEY"),
                bright_data_api_url=get_env("BRIGHT_DATA_API_URL", "https://api.brightdata.com/request"),
                log_level=get_env("LOG_LEVEL", "INFO"),
                cookie_consent=get_env_bool("COOKIE_CONSENT", True),
            )


# Global configuration instance
_config: Optional[FlightConfig] = None


def get_config() -> FlightConfig:
    """
    Get the global configuration instance.
    
    Creates a new instance from environment variables on first call,
    then returns the cached instance.
    
    Returns:
        FlightConfig instance
        
    Example:
        >>> config = get_config()
        >>> print(config.max_retries)
        3
    """
    global _config
    if _config is None:
        if PYDANTIC_SETTINGS_AVAILABLE:
            _config = FlightConfig()
        else:
            _config = FlightConfig.from_env()
    return _config


def configure(**kwargs) -> FlightConfig:
    """
    Update global configuration with new values.
    
    Creates a new configuration instance with the provided values,
    falling back to current values for unspecified options.
    
    Args:
        **kwargs: Configuration values to set
        
    Returns:
        Updated FlightConfig instance
        
    Example:
        >>> configure(max_retries=5, default_fetch_mode="fallback")
        >>> config = get_config()
        >>> print(config.max_retries)
        5
    """
    global _config
    
    # Get current config as base
    current = get_config()
    
    if PYDANTIC_SETTINGS_AVAILABLE:
        # Merge current values with new values
        current_dict = current.model_dump()
        current_dict.update(kwargs)
        _config = FlightConfig(**current_dict)
    else:
        # For dataclass, create new instance
        from dataclasses import asdict
        current_dict = asdict(current)
        current_dict.update(kwargs)
        _config = FlightConfig(**current_dict)
    
    return _config


def reset_config() -> None:
    """
    Reset configuration to defaults.
    
    Clears the cached config so the next get_config() call
    will reload from environment variables.
    """
    global _config
    _config = None


__all__ = [
    "FlightConfig",
    "get_config",
    "configure",
    "reset_config",
    "PYDANTIC_SETTINGS_AVAILABLE",
]
