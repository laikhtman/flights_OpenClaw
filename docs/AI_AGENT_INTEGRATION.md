# AI Agent Integration Guide for fast-flights

This document outlines proposed fixes and changes to make `fast-flights` work seamlessly with AI agent services like OpenClaw. The recommendations focus on improving API consistency, error handling, structured outputs, and providing MCP (Model Context Protocol) server capabilities.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [High-Priority Changes](#high-priority-changes)
3. [API Design Improvements](#api-design-improvements)
4. [Error Handling & Reliability](#error-handling--reliability)
5. [Structured Output Enhancements](#structured-output-enhancements)
6. [MCP Server Implementation](#mcp-server-implementation)
7. [Configuration Management](#configuration-management)
8. [Testing & Validation](#testing--validation)
9. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

The `fast-flights` library is a well-structured Google Flights scraper with Protobuf-based query generation. To integrate effectively with AI agents, the library needs:

- **Standardized JSON/dict outputs** for LLM consumption
- **Robust error handling** with structured error responses
- **MCP server wrapper** for tool-based agent integration
- **Pydantic models** for schema validation
- **Async support** for non-blocking operations
- **Rate limiting & retry logic** for reliability

---

## High-Priority Changes

### 1. Add Pydantic Models for Validation & Serialization

**Current Issue**: The `Result` and `Flight` dataclasses lack JSON serialization and validation.

**Proposed Fix**: Convert dataclasses to Pydantic models.

```python
# fast_flights/schema.py - PROPOSED CHANGES

from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime

class FlightSchema(BaseModel):
    """A single flight option."""
    is_best: bool = Field(description="Whether this is the best flight option")
    name: str = Field(description="Airline name(s) operating the flight")
    departure: str = Field(description="Departure time (e.g., '10:30 AM')")
    arrival: str = Field(description="Arrival time (e.g., '2:45 PM')")
    arrival_time_ahead: str = Field(default="", description="Days ahead for arrival (e.g., '+1')")
    duration: str = Field(description="Flight duration (e.g., '5h 15m')")
    stops: int = Field(description="Number of stops (0 = nonstop)")
    delay: Optional[str] = Field(default=None, description="Delay information if any")
    price: str = Field(description="Price as string (e.g., '$299')")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_best": True,
                "name": "Delta",
                "departure": "10:30 AM",
                "arrival": "2:45 PM",
                "arrival_time_ahead": "",
                "duration": "5h 15m",
                "stops": 0,
                "delay": None,
                "price": "$299"
            }
        }

class FlightSearchResult(BaseModel):
    """Result of a flight search."""
    success: bool = Field(description="Whether the search was successful")
    current_price: Literal["low", "typical", "high", "unknown"] = Field(
        description="Current price level indicator"
    )
    flights: List[FlightSchema] = Field(default_factory=list, description="List of flight options")
    search_url: Optional[str] = Field(default=None, description="Google Flights URL for this search")
    error: Optional[str] = Field(default=None, description="Error message if search failed")
    
    def to_agent_response(self) -> dict:
        """Convert to a format optimized for AI agent consumption."""
        return {
            "status": "success" if self.success else "error",
            "data": {
                "price_level": self.current_price,
                "total_options": len(self.flights),
                "best_flight": self.flights[0].model_dump() if self.flights else None,
                "all_flights": [f.model_dump() for f in self.flights],
            },
            "metadata": {
                "search_url": self.search_url,
                "error": self.error
            }
        }

class FlightSearchRequest(BaseModel):
    """Input schema for flight search - used by AI agents."""
    origin: str = Field(description="Origin airport code (e.g., 'JFK', 'LAX')", min_length=3, max_length=4)
    destination: str = Field(description="Destination airport code (e.g., 'SFO', 'ORD')", min_length=3, max_length=4)
    departure_date: str = Field(description="Departure date in YYYY-MM-DD format")
    return_date: Optional[str] = Field(default=None, description="Return date for round-trip (YYYY-MM-DD)")
    adults: int = Field(default=1, ge=1, le=9, description="Number of adult passengers")
    children: int = Field(default=0, ge=0, le=8, description="Number of child passengers")
    infants_in_seat: int = Field(default=0, ge=0, le=4, description="Number of infants in seat")
    infants_on_lap: int = Field(default=0, ge=0, le=4, description="Number of infants on lap")
    seat_class: Literal["economy", "premium-economy", "business", "first"] = Field(
        default="economy", description="Seat class"
    )
    max_stops: Optional[int] = Field(default=None, ge=0, le=2, description="Maximum number of stops")
    
    @property
    def trip_type(self) -> Literal["one-way", "round-trip"]:
        return "round-trip" if self.return_date else "one-way"
```

### 2. Create a Unified Agent-Friendly API

**Current Issue**: Multiple entry points (`get_flights`, `get_flights_from_filter`, `create_filter`) are confusing for agents.

**Proposed Fix**: Add a single, simple function for agent use.

```python
# fast_flights/agent_api.py - NEW FILE

from typing import Optional, Union
from .schema import FlightSearchRequest, FlightSearchResult, FlightSchema
from .core import get_flights
from .flights_impl import FlightData, Passengers

def search_flights(request: Union[FlightSearchRequest, dict]) -> FlightSearchResult:
    """
    AI Agent-friendly flight search API.
    
    This is the primary entry point for AI agents to search flights.
    Accepts either a FlightSearchRequest or a dictionary with the same fields.
    
    Args:
        request: Flight search parameters
        
    Returns:
        FlightSearchResult with structured flight data
    
    Example:
        >>> result = search_flights({
        ...     "origin": "JFK",
        ...     "destination": "LAX", 
        ...     "departure_date": "2025-06-15",
        ...     "adults": 2
        ... })
        >>> print(result.to_agent_response())
    """
    # Convert dict to Pydantic model if needed
    if isinstance(request, dict):
        request = FlightSearchRequest(**request)
    
    # Build flight data
    flight_data = [
        FlightData(
            date=request.departure_date,
            from_airport=request.origin.upper(),
            to_airport=request.destination.upper()
        )
    ]
    
    # Add return flight for round-trip
    if request.return_date:
        flight_data.append(
            FlightData(
                date=request.return_date,
                from_airport=request.destination.upper(),
                to_airport=request.origin.upper()
            )
        )
    
    try:
        result = get_flights(
            flight_data=flight_data,
            trip=request.trip_type,
            passengers=Passengers(
                adults=request.adults,
                children=request.children,
                infants_in_seat=request.infants_in_seat,
                infants_on_lap=request.infants_on_lap
            ),
            seat=request.seat_class,
            max_stops=request.max_stops,
            fetch_mode="fallback",  # Most reliable mode
        )
        
        if result is None:
            return FlightSearchResult(
                success=False,
                current_price="unknown",
                error="No flights found for the specified route and dates"
            )
        
        # Convert to schema
        flights = [
            FlightSchema(
                is_best=f.is_best,
                name=f.name,
                departure=f.departure,
                arrival=f.arrival,
                arrival_time_ahead=f.arrival_time_ahead,
                duration=f.duration,
                stops=f.stops,
                delay=f.delay,
                price=f.price
            )
            for f in result.flights
        ]
        
        return FlightSearchResult(
            success=True,
            current_price=result.current_price or "unknown",
            flights=flights
        )
        
    except Exception as e:
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            error=str(e)
        )
```

---

## API Design Improvements

### 3. Add Async Support

**Current Issue**: All operations are synchronous, blocking the event loop.

**Proposed Fix**: Add async versions of core functions.

```python
# fast_flights/async_core.py - NEW FILE

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from .agent_api import search_flights, FlightSearchRequest, FlightSearchResult

_executor = ThreadPoolExecutor(max_workers=4)

async def search_flights_async(
    request: FlightSearchRequest | dict
) -> FlightSearchResult:
    """
    Async version of search_flights for non-blocking operation.
    
    Useful when integrating with async AI agent frameworks.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, search_flights, request)


async def search_multiple_routes_async(
    requests: list[FlightSearchRequest | dict]
) -> list[FlightSearchResult]:
    """
    Search multiple routes concurrently.
    
    Useful for comparing different date/route combinations.
    """
    tasks = [search_flights_async(req) for req in requests]
    return await asyncio.gather(*tasks)
```

### 4. Improve Type Hints and Documentation

**Current Issue**: Some functions lack comprehensive type hints and docstrings.

**Proposed Changes in `core.py`**:

```python
def get_flights(
    *,
    flight_data: List[FlightData],
    trip: Literal["round-trip", "one-way", "multi-city"],
    passengers: Optional[Passengers] = None,
    adults: Optional[int] = None,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    seat: Literal["economy", "premium-economy", "business", "first"] = "economy",
    fetch_mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "common",
    max_stops: Optional[int] = None,
    data_source: DataSource = 'html',
    cookies: bytes | None = None,
    request_kwargs: dict | None = None,
    cookie_consent: bool = True,
) -> Union[Result, DecodedResult, None]:
    """
    Search for flights on Google Flights.
    
    This is the main entry point for flight searches. For AI agent integration,
    consider using `search_flights()` from `fast_flights.agent_api` instead.
    
    Args:
        flight_data: List of FlightData objects specifying routes and dates.
        trip: Trip type - "one-way", "round-trip", or "multi-city".
        passengers: Passengers object, or use individual passenger count args below.
        adults: Number of adult passengers (default: 1).
        children: Number of child passengers (default: 0).
        infants_in_seat: Number of infants with own seat (default: 0).
        infants_on_lap: Number of lap infants (default: 0).
        seat: Seat class - "economy", "premium-economy", "business", or "first".
        fetch_mode: 
            - "common": Direct HTTP request (fastest, may be blocked).
            - "fallback": Try common first, fallback to playwright if blocked.
            - "force-fallback": Always use playwright fallback.
            - "local": Use local playwright installation.
            - "bright-data": Use Bright Data SERP API.
        max_stops: Maximum number of stops (0-2, None for any).
        data_source: Parse from 'html' or 'js' (JavaScript data).
        cookies: Custom cookies as bytes (JSON, pickle, or raw Cookie header).
        request_kwargs: Additional kwargs passed to HTTP client.
        cookie_consent: Use embedded consent cookies if no cookies provided.
        
    Returns:
        Result or DecodedResult object with flight data, or None if no flights found.
        
    Raises:
        RuntimeError: If no flights found and no fallback available.
        AssertionError: If HTTP request fails without fallback mode.
        
    Example:
        >>> result = get_flights(
        ...     flight_data=[FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")],
        ...     trip="one-way",
        ...     seat="economy",
        ...     adults=2
        ... )
        >>> print(f"Found {len(result.flights)} flights")
    """
    # ... existing implementation
```

---

## Error Handling & Reliability

### 5. Structured Error Responses

**Current Issue**: Errors raise exceptions that agents can't easily parse.

**Proposed Fix**: Add error wrapper with structured responses.

```python
# fast_flights/errors.py - NEW FILE

from enum import Enum
from typing import Optional
from pydantic import BaseModel

class ErrorCode(str, Enum):
    """Standardized error codes for AI agent consumption."""
    INVALID_AIRPORT = "INVALID_AIRPORT"
    INVALID_DATE = "INVALID_DATE"
    NO_FLIGHTS_FOUND = "NO_FLIGHTS_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    BLOCKED = "BLOCKED"
    NETWORK_ERROR = "NETWORK_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    INVALID_PASSENGERS = "INVALID_PASSENGERS"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

class FlightSearchError(BaseModel):
    """Structured error response for AI agents."""
    code: ErrorCode
    message: str
    details: Optional[dict] = None
    recoverable: bool = True
    suggested_action: Optional[str] = None
    
    @classmethod
    def from_exception(cls, e: Exception) -> "FlightSearchError":
        """Convert an exception to a structured error."""
        error_str = str(e).lower()
        
        if "no flights found" in error_str:
            return cls(
                code=ErrorCode.NO_FLIGHTS_FOUND,
                message="No flights found for the specified route and dates",
                recoverable=True,
                suggested_action="Try different dates or nearby airports"
            )
        elif "429" in error_str or "rate" in error_str:
            return cls(
                code=ErrorCode.RATE_LIMITED,
                message="Rate limited by Google Flights",
                recoverable=True,
                suggested_action="Wait 30-60 seconds before retrying"
            )
        elif "403" in error_str or "blocked" in error_str:
            return cls(
                code=ErrorCode.BLOCKED,
                message="Request blocked by Google Flights",
                recoverable=True,
                suggested_action="Use 'fallback' or 'bright-data' fetch mode"
            )
        elif "airport" in error_str or "iata" in error_str:
            return cls(
                code=ErrorCode.INVALID_AIRPORT,
                message="Invalid airport code provided",
                recoverable=True,
                suggested_action="Verify airport codes using search_airport()"
            )
        else:
            return cls(
                code=ErrorCode.UNKNOWN_ERROR,
                message=str(e),
                recoverable=False,
                suggested_action="Check input parameters and try again"
            )

class FlightAPIException(Exception):
    """Exception with structured error information."""
    def __init__(self, error: FlightSearchError):
        self.error = error
        super().__init__(error.message)
```

### 6. Add Retry Logic with Exponential Backoff

**Proposed Addition to `core.py`**:

```python
# fast_flights/retry.py - NEW FILE

import time
import random
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
R = TypeVar('R')

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (AssertionError, RuntimeError)
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that retries a function with exponential backoff.
    
    Useful for handling transient failures when scraping Google Flights.
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        if jitter:
                            delay *= (0.5 + random.random())
                        time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator
```

---

## MCP Server Implementation

### 7. Create MCP Server for Agent Integration

**Proposed New File**: This allows `fast-flights` to be used as an MCP tool server.

```python
# fast_flights/mcp_server.py - NEW FILE

"""
MCP (Model Context Protocol) Server for fast-flights.

Run with: python -m fast_flights.mcp_server

This exposes flight search as MCP tools that can be used by
AI agents like OpenClaw, Claude, etc.
"""

import json
from typing import Any

# Note: Requires mcp package: pip install mcp
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from .agent_api import search_flights, FlightSearchRequest
from .search import search_airport
from .flights_impl import Airport

def create_mcp_server() -> "Server":
    """Create and configure the MCP server."""
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp"
        )
    
    server = Server("fast-flights")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available flight search tools."""
        return [
            Tool(
                name="search_flights",
                description="""Search for flights between airports.
                
Use this tool to find available flights, prices, and schedules.
Returns flight options with prices, times, stops, and duration.

The 'current_price' field indicates if prices are currently:
- "low": Good time to book
- "typical": Normal pricing  
- "high": Prices above average

Example: Search for flights from New York (JFK) to Los Angeles (LAX)
on June 15, 2025 for 2 adults.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Origin airport IATA code (e.g., 'JFK', 'LAX', 'ORD')",
                            "minLength": 3,
                            "maxLength": 4
                        },
                        "destination": {
                            "type": "string", 
                            "description": "Destination airport IATA code",
                            "minLength": 3,
                            "maxLength": 4
                        },
                        "departure_date": {
                            "type": "string",
                            "description": "Departure date in YYYY-MM-DD format",
                            "pattern": r"^\d{4}-\d{2}-\d{2}$"
                        },
                        "return_date": {
                            "type": "string",
                            "description": "Return date for round-trip (YYYY-MM-DD). Omit for one-way.",
                            "pattern": r"^\d{4}-\d{2}-\d{2}$"
                        },
                        "adults": {
                            "type": "integer",
                            "description": "Number of adult passengers",
                            "default": 1,
                            "minimum": 1,
                            "maximum": 9
                        },
                        "children": {
                            "type": "integer",
                            "description": "Number of child passengers (2-11 years)",
                            "default": 0,
                            "minimum": 0
                        },
                        "seat_class": {
                            "type": "string",
                            "enum": ["economy", "premium-economy", "business", "first"],
                            "description": "Seat class",
                            "default": "economy"
                        },
                        "max_stops": {
                            "type": "integer",
                            "description": "Maximum number of stops (0=nonstop, 1, 2)",
                            "minimum": 0,
                            "maximum": 2
                        }
                    },
                    "required": ["origin", "destination", "departure_date"]
                }
            ),
            Tool(
                name="search_airport",
                description="""Search for airport codes by name or city.
                
Use this tool when you know the city/airport name but not the IATA code.
Returns a list of matching airports with their codes.

Example: Search for airports in "Tokyo" or "Los Angeles".""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Airport or city name to search for"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="compare_flight_dates",
                description="""Compare flight prices across multiple dates.
                
Use this tool to help users find the cheapest days to fly.
Returns price comparisons for the specified date range.""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "Origin airport IATA code"
                        },
                        "destination": {
                            "type": "string",
                            "description": "Destination airport IATA code"
                        },
                        "dates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of dates to compare (YYYY-MM-DD format)"
                        },
                        "adults": {
                            "type": "integer",
                            "default": 1
                        }
                    },
                    "required": ["origin", "destination", "dates"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        
        if name == "search_flights":
            result = search_flights(arguments)
            response = result.to_agent_response()
            return [TextContent(
                type="text",
                text=json.dumps(response, indent=2)
            )]
        
        elif name == "search_airport":
            query = arguments.get("query", "")
            airports = search_airport(query)
            airport_list = [
                {
                    "code": airport.value,
                    "name": airport.name.replace("_", " ").title()
                }
                for airport in airports[:10]  # Limit to 10 results
            ]
            return [TextContent(
                type="text",
                text=json.dumps({
                    "query": query,
                    "results": airport_list,
                    "total": len(airports)
                }, indent=2)
            )]
        
        elif name == "compare_flight_dates":
            results = []
            for date in arguments.get("dates", []):
                req = {
                    "origin": arguments["origin"],
                    "destination": arguments["destination"],
                    "departure_date": date,
                    "adults": arguments.get("adults", 1)
                }
                result = search_flights(req)
                if result.success and result.flights:
                    cheapest = min(result.flights, key=lambda f: _parse_price(f.price))
                    results.append({
                        "date": date,
                        "cheapest_price": cheapest.price,
                        "price_level": result.current_price,
                        "options_count": len(result.flights)
                    })
                else:
                    results.append({
                        "date": date,
                        "error": result.error or "No flights found"
                    })
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "comparison": results,
                    "recommendation": _get_recommendation(results)
                }, indent=2)
            )]
        
        else:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]


def _parse_price(price_str: str) -> float:
    """Parse price string to float for comparison."""
    import re
    match = re.search(r'[\d,]+\.?\d*', price_str.replace(',', ''))
    return float(match.group()) if match else float('inf')


def _get_recommendation(results: list[dict]) -> str:
    """Generate a recommendation based on price comparison."""
    valid = [r for r in results if "cheapest_price" in r]
    if not valid:
        return "Unable to compare - no valid results"
    
    cheapest = min(valid, key=lambda r: _parse_price(r["cheapest_price"]))
    return f"Best date to fly: {cheapest['date']} at {cheapest['cheapest_price']}"


async def main():
    """Run the MCP server."""
    server = create_mcp_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### 8. Add MCP Configuration File

**Proposed New File**:

```json
// mcp.json - NEW FILE
{
    "name": "fast-flights",
    "version": "1.0.0",
    "description": "Google Flights search tool for AI agents",
    "tools": [
        {
            "name": "search_flights",
            "description": "Search for flights between airports"
        },
        {
            "name": "search_airport", 
            "description": "Find airport codes by name"
        },
        {
            "name": "compare_flight_dates",
            "description": "Compare prices across multiple dates"
        }
    ],
    "configuration": {
        "fetch_mode": {
            "type": "string",
            "enum": ["common", "fallback", "bright-data"],
            "default": "fallback",
            "description": "HTTP fetch strategy"
        },
        "bright_data_api_key": {
            "type": "string",
            "description": "Bright Data API key (optional, for bright-data mode)",
            "secret": true
        }
    }
}
```

---

## Configuration Management

### 9. Centralized Configuration

**Proposed New File**:

```python
# fast_flights/config.py - NEW FILE

from pydantic_settings import BaseSettings
from typing import Literal, Optional


class FlightConfig(BaseSettings):
    """
    Configuration for fast-flights.
    
    Settings can be provided via:
    1. Environment variables (prefixed with FAST_FLIGHTS_)
    2. .env file
    3. Direct instantiation
    """
    
    # Fetch mode
    default_fetch_mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "fallback"
    
    # Bright Data settings
    bright_data_api_key: Optional[str] = None
    bright_data_api_url: str = "https://api.brightdata.com/request"
    bright_data_serp_zone: str = "serp_api1"
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Rate limiting
    requests_per_minute: int = 30
    
    # Caching
    cache_enabled: bool = False
    cache_ttl_seconds: int = 300
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_prefix = "FAST_FLIGHTS_"
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global configuration instance
_config: Optional[FlightConfig] = None

def get_config() -> FlightConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = FlightConfig()
    return _config

def configure(**kwargs) -> FlightConfig:
    """Update global configuration."""
    global _config
    _config = FlightConfig(**kwargs)
    return _config
```

---

## Testing & Validation

### 10. Add Test Fixtures for Agent Integration

**Proposed New File**:

```python
# tests/test_agent_api.py - NEW FILE

import pytest
from fast_flights.agent_api import search_flights, FlightSearchRequest
from fast_flights.schema import FlightSearchResult

class TestAgentAPI:
    """Tests for the agent-friendly API."""
    
    def test_search_flights_with_dict(self):
        """Test that dict input works correctly."""
        request = {
            "origin": "JFK",
            "destination": "LAX",
            "departure_date": "2025-12-01",
            "adults": 1
        }
        result = search_flights(request)
        
        assert isinstance(result, FlightSearchResult)
        assert result.success or result.error is not None
    
    def test_search_flights_with_pydantic_model(self):
        """Test that Pydantic model input works correctly."""
        request = FlightSearchRequest(
            origin="SFO",
            destination="ORD",
            departure_date="2025-12-01"
        )
        result = search_flights(request)
        
        assert isinstance(result, FlightSearchResult)
    
    def test_agent_response_format(self):
        """Test the agent response format."""
        request = {"origin": "JFK", "destination": "LAX", "departure_date": "2025-12-01"}
        result = search_flights(request)
        
        response = result.to_agent_response()
        
        assert "status" in response
        assert "data" in response
        assert "metadata" in response
        assert response["status"] in ["success", "error"]
    
    def test_invalid_airport_code(self):
        """Test handling of invalid airport codes."""
        request = {"origin": "XXX", "destination": "YYY", "departure_date": "2025-12-01"}
        result = search_flights(request)
        
        # Should not crash, should return error
        assert isinstance(result, FlightSearchResult)
    
    def test_round_trip_detection(self):
        """Test that round-trip is correctly detected."""
        one_way = FlightSearchRequest(
            origin="JFK", destination="LAX", departure_date="2025-12-01"
        )
        round_trip = FlightSearchRequest(
            origin="JFK", destination="LAX", 
            departure_date="2025-12-01", return_date="2025-12-08"
        )
        
        assert one_way.trip_type == "one-way"
        assert round_trip.trip_type == "round-trip"
```

---

## Implementation Roadmap

### Phase 1: Core API Improvements (Priority: High)
1. ✅ Add Pydantic models for schema validation
2. ✅ Create unified `search_flights()` function
3. ✅ Implement structured error responses
4. ✅ Add comprehensive docstrings

### Phase 2: MCP Server (Priority: High)
1. ✅ Create MCP server implementation
2. ✅ Define tool schemas
3. ✅ Add configuration file
4. ⬜ Test with OpenClaw and Claude Desktop

### Phase 3: Reliability (Priority: Medium)
1. ⬜ Add retry logic with exponential backoff
2. ⬜ Implement rate limiting
3. ⬜ Add request caching

### Phase 4: Async Support (Priority: Medium)
1. ⬜ Add async wrapper functions
2. ⬜ Support concurrent route searches
3. ⬜ Optimize thread pool

### Phase 5: Additional Features (Priority: Low)
1. ⬜ Add price alerts/tracking
2. ⬜ Implement flexible date search
3. ⬜ Add airline filtering

---

## Updated `pyproject.toml` Dependencies

```toml
# Add to pyproject.toml

[project.optional-dependencies]
agent = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]
mcp = [
    "mcp>=1.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]
all = [
    "playwright",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "mcp>=1.0",
]

[project.scripts]
fast-flights-mcp = "fast_flights.mcp_server:main"
```

---

## Updated `__init__.py` Exports

```python
# Add to fast_flights/__init__.py

# Agent API exports
try:
    from .agent_api import search_flights, FlightSearchRequest, FlightSearchResult
    from .errors import FlightSearchError, ErrorCode, FlightAPIException
except ImportError:
    # Pydantic not installed
    pass

__all__ = [
    # Existing exports
    "Airport",
    "TFSData", 
    "create_filter",
    "FlightData",
    "Passengers",
    "get_flights_from_filter",
    "Result",
    "Flight",
    "search_airport",
    "Cookies",
    "get_flights",
    # New agent-friendly exports
    "search_flights",
    "FlightSearchRequest", 
    "FlightSearchResult",
    "FlightSearchError",
    "ErrorCode",
]
```

---

## Summary

These changes will transform `fast-flights` into an AI-agent-ready library with:

| Feature | Current State | After Changes |
|---------|---------------|---------------|
| JSON Output | Manual conversion | Built-in `model_dump()` |
| Error Handling | Exceptions | Structured `FlightSearchError` |
| Schema Validation | None | Pydantic models |
| MCP Support | None | Full MCP server |
| Async Support | None | Async wrappers |
| Documentation | Basic | Comprehensive |
| Configuration | Env vars scattered | Centralized config |

The library will be usable as:
1. **Direct Python import** for scripts
2. **MCP tool server** for AI agents
3. **CLI tool** for command-line use
4. **HTTP API** (future, with FastAPI wrapper)
