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

# Type definitions and utilities (always available)
from .types import (
    SeatClass, TripType, FetchMode, DataSource, PriceLevel,
    DummyResponse, SEAT_CLASSES, TRIP_TYPES, FETCH_MODES,
)
from .utils import (
    extract_price, format_duration, format_time,
    validate_airport_code, validate_date, build_google_flights_url,
)

# Agent API imports (optional - requires pydantic)
try:
    from .agent_api import search_flights, search_airports, compare_flight_dates
    from .schema_v2 import FlightSearchRequest, FlightSearchResult, FlightSchema, PYDANTIC_AVAILABLE
    from .errors import ErrorCode, FlightSearchError
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
    PYDANTIC_AVAILABLE = False

# Configuration and reliability (always available)
from .config import FlightConfig, get_config, configure, reset_config
from .retry import retry_with_backoff, RetryContext, is_retryable_error
from .rate_limit import RateLimiter, get_rate_limiter, rate_limited

# Async API (optional - requires pydantic)
try:
    from .async_api import (
        search_flights_async,
        search_airports_async,
        compare_flight_dates_async,
        search_multiple_routes,
        search_date_range,
        run_in_executor,
        get_executor,
        shutdown_executor,
    )
    _ASYNC_API_AVAILABLE = True
except ImportError:
    _ASYNC_API_AVAILABLE = False
    search_flights_async = None  # type: ignore
    search_airports_async = None  # type: ignore
    compare_flight_dates_async = None  # type: ignore
    search_multiple_routes = None  # type: ignore
    search_date_range = None  # type: ignore
    run_in_executor = None  # type: ignore
    get_executor = None  # type: ignore
    shutdown_executor = None  # type: ignore

# Price Tracking API (optional - requires pydantic)
try:
    from .price_storage import (
        PriceRecord,
        PriceAlert,
        TrackedRoute,
        PriceStorageBackend,
        SQLitePriceStorage,
        get_price_storage,
        reset_price_storage,
    )
    from .price_tracker import (
        PriceTracker,
        PriceChange,
        WebhookAlertHandler,
        EmailAlertHandler,
        get_price_tracker,
        reset_price_tracker,
    )
    _PRICE_TRACKING_AVAILABLE = True
except ImportError:
    _PRICE_TRACKING_AVAILABLE = False
    PriceRecord = None  # type: ignore
    PriceAlert = None  # type: ignore
    TrackedRoute = None  # type: ignore
    PriceStorageBackend = None  # type: ignore
    SQLitePriceStorage = None  # type: ignore
    get_price_storage = None  # type: ignore
    reset_price_storage = None  # type: ignore
    PriceTracker = None  # type: ignore
    PriceChange = None  # type: ignore
    WebhookAlertHandler = None  # type: ignore
    EmailAlertHandler = None  # type: ignore
    get_price_tracker = None  # type: ignore
    reset_price_tracker = None  # type: ignore

# Flexible Date Search API (optional - requires agent API)
try:
    from .flexible_dates import (
        DatePrice,
        FlexibleSearchResult,
        CalendarHeatmap,
        search_flexible_dates,
        search_weekend_flights,
        search_weekday_flights,
        get_calendar_heatmap,
        suggest_best_dates,
        generate_date_range,
        generate_weekend_dates,
        generate_weekday_dates,
        generate_month_dates,
    )
    _FLEX_DATES_AVAILABLE = True
except ImportError:
    _FLEX_DATES_AVAILABLE = False
    DatePrice = None  # type: ignore
    FlexibleSearchResult = None  # type: ignore
    CalendarHeatmap = None  # type: ignore
    search_flexible_dates = None  # type: ignore
    search_weekend_flights = None  # type: ignore
    search_weekday_flights = None  # type: ignore
    get_calendar_heatmap = None  # type: ignore
    suggest_best_dates = None  # type: ignore
    generate_date_range = None  # type: ignore
    generate_weekend_dates = None  # type: ignore
    generate_weekday_dates = None  # type: ignore
    generate_month_dates = None  # type: ignore

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
    # Type definitions
    "SeatClass",
    "TripType",
    "FetchMode",
    "DataSource",
    "PriceLevel",
    "DummyResponse",
    "SEAT_CLASSES",
    "TRIP_TYPES",
    "FETCH_MODES",
    # Utilities
    "extract_price",
    "format_duration",
    "format_time",
    "validate_airport_code",
    "validate_date",
    "build_google_flights_url",
    # Agent-friendly API (requires pydantic)
    "search_flights",
    "search_airports",
    "compare_flight_dates",
    "FlightSearchRequest",
    "FlightSearchResult",
    "FlightSchema",
    "ErrorCode",
    "FlightSearchError",
    "PYDANTIC_AVAILABLE",
    # Configuration and reliability
    "FlightConfig",
    "get_config",
    "configure",
    "reset_config",
    "retry_with_backoff",
    "RetryContext",
    "is_retryable_error",
    "RateLimiter",
    "get_rate_limiter",
    "rate_limited",
    # Async API (requires pydantic)
    "search_flights_async",
    "search_airports_async",
    "compare_flight_dates_async",
    "search_multiple_routes",
    "search_date_range",
    "run_in_executor",
    "get_executor",
    "shutdown_executor",
    # Price Tracking API (requires pydantic)
    "PriceRecord",
    "PriceAlert",
    "TrackedRoute",
    "PriceStorageBackend",
    "SQLitePriceStorage",
    "get_price_storage",
    "reset_price_storage",
    "PriceTracker",
    "PriceChange",
    "WebhookAlertHandler",
    "EmailAlertHandler",
    "get_price_tracker",
    "reset_price_tracker",
    # Flexible Date Search API (requires pydantic)
    "DatePrice",
    "FlexibleSearchResult",
    "CalendarHeatmap",
    "search_flexible_dates",
    "search_weekend_flights",
    "search_weekday_flights",
    "get_calendar_heatmap",
    "suggest_best_dates",
    "generate_date_range",
    "generate_weekend_dates",
    "generate_weekday_dates",
    "generate_month_dates",
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
