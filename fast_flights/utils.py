"""
Shared utilities for fast-flights.

This module provides common helper functions used across the codebase,
reducing code duplication and ensuring consistent behavior.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def extract_price(price_str: str) -> float:
    """
    Extract numeric price value from a price string.
    
    Handles various formats including currency symbols, thousands separators,
    and decimal points.
    
    Args:
        price_str: Price string (e.g., "$1,299", "€250.50", "£99")
        
    Returns:
        Numeric price value, or float('inf') if parsing fails
        
    Examples:
        >>> extract_price("$1,299")
        1299.0
        >>> extract_price("€250.50")
        250.5
        >>> extract_price("N/A")
        inf
    """
    if not price_str:
        return float('inf')
    
    # Remove thousands separators and find numeric value
    cleaned = price_str.replace(',', '').replace(' ', '')
    match = re.search(r'[\d]+\.?\d*', cleaned)
    
    if match:
        try:
            return float(match.group())
        except ValueError:
            return float('inf')
    
    return float('inf')


def format_duration(minutes: int) -> str:
    """
    Format duration in minutes to human-readable string.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Formatted string like "5h 30m"
        
    Examples:
        >>> format_duration(330)
        "5h 30m"
        >>> format_duration(60)
        "1h 0m"
    """
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def format_time(hour: int, minute: int) -> str:
    """
    Format hour and minute to time string.
    
    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        
    Returns:
        Formatted time string like "14:30"
        
    Examples:
        >>> format_time(14, 30)
        "14:30"
        >>> format_time(9, 5)
        "09:05"
    """
    return f"{hour:02d}:{minute:02d}"


def safe_get(obj: Any, *attrs: str, default: Any = None) -> Any:
    """
    Safely get nested attributes from an object.
    
    Args:
        obj: Object to get attributes from
        *attrs: Attribute names to traverse
        default: Default value if attribute doesn't exist
        
    Returns:
        The attribute value or default
        
    Examples:
        >>> safe_get(result, 'itinerary', 'price', default=0)
    """
    for attr in attrs:
        try:
            obj = getattr(obj, attr, None)
            if obj is None:
                return default
        except Exception:
            return default
    return obj


def truncate_string(s: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        s: String to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append if truncated
        
    Returns:
        Truncated string with suffix if needed
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def validate_airport_code(code: str) -> str:
    """
    Validate and normalize an airport IATA code.
    
    Args:
        code: Airport code to validate
        
    Returns:
        Uppercase 3-letter code
        
    Raises:
        ValueError: If code is not a valid IATA format
    """
    code = code.strip().upper()
    if not re.match(r'^[A-Z]{3}$', code):
        raise ValueError(f"Invalid airport code: {code}. Must be 3 letters.")
    return code


def validate_date(date_str: str) -> str:
    """
    Validate a date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Validated date string
        
    Raises:
        ValueError: If date format is invalid
    """
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")
    
    # Validate actual date values
    try:
        from datetime import datetime
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date: {date_str}. {e}")
    
    return date_str


def build_google_flights_url(tfs_b64: str) -> str:
    """
    Build a Google Flights URL from an encoded TFS parameter.
    
    Args:
        tfs_b64: Base64-encoded TFS filter string
        
    Returns:
        Full Google Flights URL
    """
    return f"https://www.google.com/travel/flights?tfs={tfs_b64}"


__all__ = [
    "extract_price",
    "format_duration",
    "format_time",
    "safe_get",
    "truncate_string",
    "validate_airport_code",
    "validate_date",
    "build_google_flights_url",
]
