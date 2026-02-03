"""
AI Agent-friendly API for fast-flights.

This module provides a simplified, unified interface for AI agents to search flights.
It handles all the complexity of filter creation, error handling, and response formatting.

Usage:
    >>> from fast_flights.agent_api import search_flights
    >>> result = search_flights({
    ...     "origin": "JFK",
    ...     "destination": "LAX",
    ...     "departure_date": "2025-06-15",
    ...     "adults": 2
    ... })
    >>> print(result.to_agent_response())
"""

from typing import Union, Optional, Literal, List
import logging

from .schema_v2 import (
    FlightSearchRequest,
    FlightSearchResult,
    FlightSchema,
    PYDANTIC_AVAILABLE,
)
from .core import get_flights
from .flights_impl import FlightData, Passengers
from .errors import FlightSearchError, ErrorCode
from .utils import extract_price, format_duration, format_time

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions (extracted for testability and clarity)
# ============================================================================

def _validate_request(request: Union["FlightSearchRequest", dict]) -> "FlightSearchRequest":
    """
    Validate and normalize the search request.
    
    Args:
        request: Either a FlightSearchRequest or dict
        
    Returns:
        Validated FlightSearchRequest
        
    Raises:
        ValueError: If validation fails
    """
    if isinstance(request, dict):
        request = FlightSearchRequest(**request)
    request.validate_passengers()
    return request


def _build_flight_data(request: "FlightSearchRequest") -> List[FlightData]:
    """Build FlightData list from request."""
    flight_data = [
        FlightData(
            date=request.departure_date,
            from_airport=request.origin.upper(),
            to_airport=request.destination.upper()
        )
    ]
    
    if request.return_date:
        flight_data.append(
            FlightData(
                date=request.return_date,
                from_airport=request.destination.upper(),
                to_airport=request.origin.upper()
            )
        )
    
    return flight_data


def _build_passengers(request: "FlightSearchRequest") -> Passengers:
    """Build Passengers object from request."""
    return Passengers(
        adults=request.adults,
        children=request.children,
        infants_in_seat=request.infants_in_seat,
        infants_on_lap=request.infants_on_lap
    )


def _generate_search_url(
    flight_data: List[FlightData],
    request: "FlightSearchRequest",
    passengers: Passengers
) -> Optional[str]:
    """Generate Google Flights search URL."""
    try:
        from .filter import create_filter
        from .utils import build_google_flights_url
        
        tfs = create_filter(
            flight_data=flight_data,
            trip=request.trip_type,
            passengers=passengers,
            seat=request.seat_class,
            max_stops=request.max_stops
        )
        b64 = tfs.as_b64().decode('utf-8')
        return build_google_flights_url(b64)
    except Exception:
        return None


def _convert_result_flights(result) -> "tuple[List[FlightSchema], str]":
    """
    Convert search result to FlightSchema list.
    
    Returns:
        Tuple of (flights list, current_price)
    """
    if hasattr(result, 'flights'):
        # Standard Result object
        flights = [
            FlightSchema(
                is_best=f.is_best,
                name=f.name,
                departure=f.departure,
                arrival=f.arrival,
                arrival_time_ahead=getattr(f, 'arrival_time_ahead', ''),
                duration=f.duration,
                stops=f.stops if isinstance(f.stops, int) else 0,
                delay=getattr(f, 'delay', None),
                price=f.price
            )
            for f in result.flights
        ]
        current_price = getattr(result, 'current_price', 'unknown') or 'unknown'
        return flights, current_price
    
    elif hasattr(result, 'best') and hasattr(result, 'other'):
        # DecodedResult object (from js data source)
        flights = []
        for i, itinerary in enumerate(result.best + result.other):
            is_best = i < len(result.best)
            airline_names = getattr(itinerary, 'airline_names', [])
            name = ', '.join(airline_names) if airline_names else 'Unknown'
            
            dep_time = getattr(itinerary, 'departure_time', (0, 0))
            arr_time = getattr(itinerary, 'arrival_time', (0, 0))
            
            flights.append(FlightSchema(
                is_best=is_best,
                name=name,
                departure=format_time(*dep_time) if dep_time else "",
                arrival=format_time(*arr_time) if arr_time else "",
                arrival_time_ahead="",
                duration=format_duration(itinerary.travel_time) if hasattr(itinerary, 'travel_time') else "",
                stops=len(getattr(itinerary, 'layovers', [])),
                delay=None,
                price=f"${itinerary.itinerary_summary.price}" if hasattr(itinerary, 'itinerary_summary') else "N/A"
            ))
        return flights, "unknown"
    
    return [], "unknown"


# ============================================================================
# Main API Functions
# ============================================================================


def search_flights(
    request: Union["FlightSearchRequest", dict],
    *,
    fetch_mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "fallback",
    include_url: bool = True,
) -> "FlightSearchResult":
    """
    AI Agent-friendly flight search API.
    
    This is the primary entry point for AI agents to search flights.
    Accepts either a FlightSearchRequest Pydantic model or a dictionary.
    
    Args:
        request: Flight search parameters. Can be:
            - FlightSearchRequest: Pydantic model with validated fields
            - dict: Dictionary with the same field names
        fetch_mode: HTTP fetching strategy:
            - "common": Direct request (fastest, may be blocked)
            - "fallback": Try direct, fall back to playwright (recommended)
            - "force-fallback": Always use playwright
            - "local": Use local playwright installation
            - "bright-data": Use Bright Data SERP API
        include_url: Whether to include Google Flights URL in response
        
    Returns:
        FlightSearchResult with:
            - success: bool indicating if search succeeded
            - current_price: "low", "typical", "high", or "unknown"
            - flights: List of FlightSchema objects
            - search_url: Google Flights URL (if include_url=True)
            - error: Error message if search failed
    
    Examples:
        Basic one-way search:
        >>> result = search_flights({
        ...     "origin": "JFK",
        ...     "destination": "LAX",
        ...     "departure_date": "2025-06-15"
        ... })
        
        Round-trip with options:
        >>> result = search_flights({
        ...     "origin": "SFO",
        ...     "destination": "LHR",
        ...     "departure_date": "2025-07-01",
        ...     "return_date": "2025-07-15",
        ...     "adults": 2,
        ...     "seat_class": "business",
        ...     "max_stops": 1
        ... })
        
        Get agent-friendly response:
        >>> response = result.to_agent_response()
        >>> print(response["status"])  # "success" or "error"
    
    Note:
        This function never raises exceptions. All errors are captured
        in the FlightSearchResult.error field for safe agent consumption.
    """
    if not PYDANTIC_AVAILABLE:
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            error="Pydantic is required for agent API. Install with: pip install pydantic"
        )
    
    # Validate and normalize request
    try:
        request = _validate_request(request)
    except Exception as e:
        logger.warning(f"Invalid request parameters: {e}")
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            error=f"Invalid request parameters: {str(e)}"
        )
    
    # Build search components
    flight_data = _build_flight_data(request)
    passengers = _build_passengers(request)
    search_url = _generate_search_url(flight_data, request, passengers) if include_url else None
    
    # Execute the search
    try:
        result = get_flights(
            flight_data=flight_data,
            trip=request.trip_type,
            passengers=passengers,
            seat=request.seat_class,
            max_stops=request.max_stops,
            fetch_mode=fetch_mode,
        )
        
        if result is None:
            return FlightSearchResult(
                success=False,
                current_price="unknown",
                search_url=search_url,
                error="No flights found for the specified route and dates"
            )
        
        # Convert result to schema
        flights, current_price = _convert_result_flights(result)
        
        if not flights and not hasattr(result, 'flights') and not hasattr(result, 'best'):
            return FlightSearchResult(
                success=False,
                current_price="unknown",
                search_url=search_url,
                error="Unexpected response format from flight search"
            )
        
        return FlightSearchResult(
            success=True,
            current_price=current_price,
            flights=flights,
            search_url=search_url
        )
        
    except AssertionError as e:
        # HTTP errors
        error = FlightSearchError.from_exception(e)
        logger.warning(f"Flight search HTTP error: {error.message}")
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            search_url=search_url,
            error=error.message
        )
        
    except RuntimeError as e:
        # Parsing errors (no flights found, etc.)
        error = FlightSearchError.from_exception(e)
        logger.warning(f"Flight search runtime error: {error.message}")
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            search_url=search_url,
            error=error.message
        )
        
    except Exception as e:
        # Unexpected errors
        error = FlightSearchError.from_exception(e)
        logger.error(f"Unexpected flight search error: {e}", exc_info=True)
        return FlightSearchResult(
            success=False,
            current_price="unknown",
            search_url=search_url,
            error=f"Unexpected error: {str(e)}"
        )


def search_airports(query: str, limit: int = 10) -> List[dict]:
    """
    Search for airports by name or city.
    
    This is a convenience wrapper around search_airport for AI agents.
    
    Args:
        query: Search query (airport name, city, or partial match)
        limit: Maximum number of results to return
        
    Returns:
        List of dicts with 'code' and 'name' keys
        
    Example:
        >>> airports = search_airports("tokyo")
        >>> print(airports[0])
        {'code': 'NRT', 'name': 'Tokyo Narita International Airport'}
    """
    from .search import search_airport
    
    airports = search_airport(query)[:limit]
    return [
        {
            "code": airport.value,
            "name": airport.name.replace("_", " ").title()
        }
        for airport in airports
    ]


def compare_flight_dates(
    origin: str,
    destination: str,
    dates: List[str],
    adults: int = 1,
    seat_class: Literal["economy", "premium-economy", "business", "first"] = "economy",
) -> dict:
    """
    Compare flight prices across multiple dates.
    
    Useful for finding the cheapest days to fly.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        dates: List of dates to compare (YYYY-MM-DD format)
        adults: Number of adult passengers
        seat_class: Seat class
        
    Returns:
        Dict with 'comparison' list and 'recommendation' string
        
    Example:
        >>> result = compare_flight_dates(
        ...     "JFK", "LAX",
        ...     ["2025-06-15", "2025-06-16", "2025-06-17"]
        ... )
        >>> print(result["recommendation"])
        "Best date to fly: 2025-06-16 at $249"
    """
    import re
    
    results = []
    for date in dates:
        search_result = search_flights({
            "origin": origin,
            "destination": destination,
            "departure_date": date,
            "adults": adults,
            "seat_class": seat_class
        })
        
        if search_result.success and search_result.flights:
            # Find cheapest flight using shared extract_price
            cheapest = min(search_result.flights, key=lambda f: extract_price(f.price))
            results.append({
                "date": date,
                "cheapest_price": cheapest.price,
                "price_level": search_result.current_price,
                "options_count": len(search_result.flights),
                "cheapest_airline": cheapest.name,
                "cheapest_duration": cheapest.duration,
                "cheapest_stops": cheapest.stops
            })
        else:
            results.append({
                "date": date,
                "error": search_result.error or "No flights found"
            })
    
    # Generate recommendation
    valid_results = [r for r in results if "cheapest_price" in r]
    if valid_results:
        cheapest_day = min(valid_results, key=lambda r: extract_price(r["cheapest_price"]))
        recommendation = f"Best date to fly: {cheapest_day['date']} at {cheapest_day['cheapest_price']}"
    else:
        recommendation = "Unable to compare - no valid results found"
    
    return {
        "comparison": results,
        "recommendation": recommendation,
        "route": f"{origin} → {destination}",
        "dates_searched": len(dates)
    }


__all__ = [
    "search_flights",
    "search_airports",
    "compare_flight_dates",
    "FlightSearchRequest",
    "FlightSearchResult",
    "FlightSchema",
]
