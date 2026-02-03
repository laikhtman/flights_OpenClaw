"""
Shared type definitions for fast-flights.

This module provides centralized type aliases and protocols used across
the codebase, ensuring consistency and reducing duplication.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

# ============================================================================
# Type Aliases
# ============================================================================

SeatClass = Literal["economy", "premium-economy", "business", "first"]
"""Seat class options for flight search."""

TripType = Literal["round-trip", "one-way", "multi-city"]
"""Trip type options for flight search."""

FetchMode = Literal["common", "fallback", "force-fallback", "local", "bright-data"]
"""
Fetch mode for retrieving flight data.

- "common": Direct HTTP request (fastest, may be blocked)
- "fallback": Try common first, fall back to playwright if blocked
- "force-fallback": Always use remote playwright service
- "local": Use local playwright installation
- "bright-data": Use Bright Data SERP API (requires API key)
"""

DataSource = Literal["html", "js"]
"""Data source for parsing: 'html' for HTML parsing, 'js' for JavaScript data extraction."""

PriceLevel = Literal["low", "typical", "high"]
"""Price level indicator from Google Flights."""


# ============================================================================
# Protocols (Interfaces)
# ============================================================================

@runtime_checkable
class ResponseProtocol(Protocol):
    """Protocol for HTTP response objects."""
    
    @property
    def status_code(self) -> int:
        """HTTP status code."""
        ...
    
    @property
    def text(self) -> str:
        """Response body as text."""
        ...
    
    @property
    def text_markdown(self) -> str:
        """Response body formatted for error messages."""
        ...


# ============================================================================
# Shared Response Class
# ============================================================================

@dataclass
class DummyResponse:
    """
    A simple response object for playwright-based fetchers.
    
    This provides a consistent interface matching ResponseProtocol
    for use with fallback and local playwright implementations.
    
    Attributes:
        status_code: HTTP status code (typically 200 for success)
        text: The response body text
        text_markdown: Same as text, used for error message formatting
    """
    status_code: int
    text: str
    text_markdown: str = ""
    
    def __post_init__(self):
        if not self.text_markdown:
            self.text_markdown = self.text


# ============================================================================
# Constants
# ============================================================================

SEAT_CLASSES: tuple[SeatClass, ...] = ("economy", "premium-economy", "business", "first")
"""All valid seat class values."""

TRIP_TYPES: tuple[TripType, ...] = ("round-trip", "one-way", "multi-city")
"""All valid trip type values."""

FETCH_MODES: tuple[FetchMode, ...] = ("common", "fallback", "force-fallback", "local", "bright-data")
"""All valid fetch mode values."""


__all__ = [
    # Type aliases
    "SeatClass",
    "TripType",
    "FetchMode",
    "DataSource",
    "PriceLevel",
    # Protocols
    "ResponseProtocol",
    # Classes
    "DummyResponse",
    # Constants
    "SEAT_CLASSES",
    "TRIP_TYPES",
    "FETCH_MODES",
]
