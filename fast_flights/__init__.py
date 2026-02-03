"""
fast-flights: A fast, robust Google Flights scraper (API) for Python.

This library provides tools to search for flights on Google Flights and parse
the results. It uses Base64-encoded Protobuf strings to generate search queries.

Quick Start:
    >>> from fast_flights import get_flights, FlightData, Passengers
    >>> result = get_flights(
    ...     flight_data=[FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")],
    ...     trip="one-way",
    ...     seat="economy",
    ...     adults=2
    ... )
    >>> print(f"Found {len(result.flights)} flights")

For AI Agent Integration:
    >>> from fast_flights import search_flights
    >>> result = search_flights({
    ...     "origin": "JFK",
    ...     "destination": "LAX",
    ...     "departure_date": "2025-06-15"
    ... })
    >>> print(result.to_agent_response())

Main Functions:
    - get_flights(): Search for flights with convenient parameters
    - search_flights(): AI agent-friendly search with structured responses
    - create_filter(): Create a search filter for advanced usage
    - search_airport(): Find airport codes by name

Classes:
    - FlightData: Represents a single flight leg (date, origin, destination)
    - Passengers: Specifies passenger counts by type
    - Result: Search results with flights list
    - FlightSearchResult: Agent-friendly result with error handling
"""

# Lazy import Cookies to avoid heavy protobuf dependencies during import-time in tests
def get_cookies_class():
    from .cookies_impl import Cookies
    return Cookies

from .core import get_flights_from_filter, get_flights
from .filter import create_filter
from .flights_impl import Airport, FlightData, Passengers, TFSData
from .schema import Flight, Result
from .search import search_airport

# Agent API imports (optional - requires pydantic)
try:
    from .agent_api import search_flights, search_airports, compare_flight_dates
    from .schema_v2 import FlightSearchRequest, FlightSearchResult, FlightSchema, PYDANTIC_AVAILABLE
    from .errors import ErrorCode, FlightSearchError, FlightAPIException
    _AGENT_API_AVAILABLE = True
except ImportError:
    _AGENT_API_AVAILABLE = False
    # Create placeholders for when pydantic is not installed
    search_flights = None  # type: ignore
    search_airports = None  # type: ignore
    compare_flight_dates = None  # type: ignore
    FlightSearchRequest = None  # type: ignore
    FlightSearchResult = None  # type: ignore
    FlightSchema = None  # type: ignore
    ErrorCode = None  # type: ignore
    FlightSearchError = None  # type: ignore
    FlightAPIException = None  # type: ignore
    PYDANTIC_AVAILABLE = False

__all__ = [
    # Core API
    "Airport",
    "TFSData",
    "create_filter",
    "FlightData",
    "Passengers",
    "get_flights_from_filter",
    "get_flights",
    "Result",
    "Flight",
    "search_airport",
    "Cookies",
    # Agent-friendly API (requires pydantic)
    "search_flights",
    "search_airports",
    "compare_flight_dates",
    "FlightSearchRequest",
    "FlightSearchResult",
    "FlightSchema",
    "ErrorCode",
    "FlightSearchError",
    "FlightAPIException",
    "PYDANTIC_AVAILABLE",
]

# Backwards-compatible name: try to resolve Cookies lazily if accessed
try:
    Cookies = get_cookies_class()
except Exception:
    # If import fails, expose a simple proxy that will import when used
    class _CookiesProxy:
        def __getattr__(self, name):
            _Cookies = get_cookies_class()
            return getattr(_Cookies, name)

    Cookies = _CookiesProxy()
