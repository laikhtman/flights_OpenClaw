"""
Async API for fast-flights.

Provides async wrappers for flight search operations, enabling:
- Non-blocking flight searches
- Concurrent multi-route searches
- Integration with async frameworks (FastAPI, aiohttp, etc.)

Example:
    import asyncio
    from fast_flights import search_flights_async, search_multiple_routes

    async def main():
        # Single async search
        result = await search_flights_async({
            "origin": "JFK",
            "destination": "LAX",
            "departure_date": "2025-06-15"
        })
        
        # Concurrent multi-route search
        routes = [
            {"origin": "JFK", "destination": "LAX", "departure_date": "2025-06-15"},
            {"origin": "SFO", "destination": "ORD", "departure_date": "2025-06-15"},
            {"origin": "MIA", "destination": "SEA", "departure_date": "2025-06-15"},
        ]
        results = await search_multiple_routes(routes)
    
    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, TypeVar
from functools import partial

# Type variable for generic async wrapper
T = TypeVar("T")

# Default thread pool for running sync operations
_executor: Optional[ThreadPoolExecutor] = None
_max_workers: int = 10


def get_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """
    Get or create the thread pool executor for async operations.
    
    Args:
        max_workers: Maximum number of worker threads. Uses default if not specified.
        
    Returns:
        ThreadPoolExecutor instance.
    """
    global _executor, _max_workers
    
    if max_workers is not None:
        _max_workers = max_workers
        
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(max_workers=_max_workers)
    
    return _executor


def shutdown_executor(wait: bool = True) -> None:
    """
    Shutdown the thread pool executor.
    
    Args:
        wait: If True, wait for all pending futures to complete.
    """
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None


async def run_in_executor(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any
) -> T:
    """
    Run a synchronous function in the thread pool executor.
    
    Args:
        func: Synchronous function to run.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.
        
    Returns:
        The result of the function call.
        
    Example:
        result = await run_in_executor(sync_function, arg1, arg2, key=value)
    """
    loop = asyncio.get_event_loop()
    executor = get_executor()
    
    if kwargs:
        func = partial(func, **kwargs)
    
    return await loop.run_in_executor(executor, func, *args)


# Import agent API functions (optional - requires pydantic)
try:
    from .agent_api import search_flights as _search_flights_sync
    from .agent_api import search_airports as _search_airports_sync
    from .agent_api import compare_flight_dates as _compare_flight_dates_sync
    from .schema_v2 import FlightSearchResult
    _AGENT_API_AVAILABLE = True
except ImportError:
    _AGENT_API_AVAILABLE = False
    _search_flights_sync = None
    _search_airports_sync = None
    _compare_flight_dates_sync = None
    FlightSearchResult = None


async def search_flights_async(
    request: Dict[str, Any],
    fetch_mode: Optional[str] = None,
) -> "FlightSearchResult":
    """
    Async version of search_flights.
    
    Searches for flights asynchronously without blocking the event loop.
    
    Args:
        request: Flight search parameters as a dictionary.
            - origin (str): Origin airport IATA code (e.g., "JFK")
            - destination (str): Destination airport IATA code (e.g., "LAX")
            - departure_date (str): Departure date in YYYY-MM-DD format
            - return_date (str, optional): Return date for round-trip
            - adults (int, optional): Number of adult passengers (default: 1)
            - children (int, optional): Number of child passengers
            - infants_in_seat (int, optional): Number of infants in seat
            - infants_on_lap (int, optional): Number of infants on lap
            - seat_class (str, optional): "economy", "premium_economy", "business", "first"
            - max_stops (int, optional): Maximum number of stops (0-2)
        fetch_mode: Override the default fetch mode.
        
    Returns:
        FlightSearchResult with success/error status and flight data.
        
    Raises:
        ImportError: If pydantic is not installed.
        
    Example:
        result = await search_flights_async({
            "origin": "JFK",
            "destination": "LAX", 
            "departure_date": "2025-06-15",
            "adults": 2
        })
        if result.success:
            print(result.summary())
    """
    if not _AGENT_API_AVAILABLE:
        raise ImportError(
            "Async API requires pydantic. Install with: pip install fast-flights[agent]"
        )
    
    kwargs = {}
    if fetch_mode:
        kwargs["fetch_mode"] = fetch_mode
    
    return await run_in_executor(_search_flights_sync, request, **kwargs)


async def search_airports_async(query: str) -> List[Dict[str, str]]:
    """
    Async version of search_airports.
    
    Search for airports by city name, airport name, or IATA code.
    
    Args:
        query: Search query (city name, airport name, or partial IATA code).
        
    Returns:
        List of matching airports with code, name, and city.
        
    Example:
        airports = await search_airports_async("new york")
        # [{"code": "JFK", "name": "John F. Kennedy...", "city": "New York"}]
    """
    if not _AGENT_API_AVAILABLE:
        raise ImportError(
            "Async API requires pydantic. Install with: pip install fast-flights[agent]"
        )
    
    return await run_in_executor(_search_airports_sync, query)


async def compare_flight_dates_async(
    origin: str,
    destination: str,
    dates: List[str],
    adults: int = 1,
    seat_class: str = "economy",
    fetch_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Async version of compare_flight_dates.
    
    Compare flight prices across multiple dates concurrently.
    
    Args:
        origin: Origin airport IATA code.
        destination: Destination airport IATA code.
        dates: List of dates to compare (YYYY-MM-DD format).
        adults: Number of adult passengers.
        seat_class: Seat class preference.
        fetch_mode: Override the default fetch mode.
        
    Returns:
        Dictionary with comparison results and best date recommendation.
        
    Example:
        result = await compare_flight_dates_async(
            origin="JFK",
            destination="LAX",
            dates=["2025-06-15", "2025-06-16", "2025-06-17"]
        )
        print(f"Best date: {result['best_date']}")
    """
    if not _AGENT_API_AVAILABLE:
        raise ImportError(
            "Async API requires pydantic. Install with: pip install fast-flights[agent]"
        )
    
    kwargs = {"adults": adults, "seat_class": seat_class}
    if fetch_mode:
        kwargs["fetch_mode"] = fetch_mode
    
    return await run_in_executor(
        _compare_flight_dates_sync, origin, destination, dates, **kwargs
    )


async def search_multiple_routes(
    routes: List[Dict[str, Any]],
    fetch_mode: Optional[str] = None,
    max_concurrent: Optional[int] = None,
) -> List["FlightSearchResult"]:
    """
    Search multiple flight routes concurrently.
    
    Performs parallel searches for multiple routes, significantly reducing
    total search time compared to sequential searches.
    
    Args:
        routes: List of route dictionaries, each containing:
            - origin (str): Origin airport IATA code
            - destination (str): Destination airport IATA code
            - departure_date (str): Departure date (YYYY-MM-DD)
            - Plus any other search parameters
        fetch_mode: Fetch mode to use for all searches.
        max_concurrent: Maximum concurrent searches. Defaults to len(routes).
        
    Returns:
        List of FlightSearchResult objects in the same order as input routes.
        
    Example:
        routes = [
            {"origin": "JFK", "destination": "LAX", "departure_date": "2025-06-15"},
            {"origin": "SFO", "destination": "ORD", "departure_date": "2025-06-15"},
            {"origin": "MIA", "destination": "SEA", "departure_date": "2025-06-15"},
        ]
        results = await search_multiple_routes(routes)
        
        for route, result in zip(routes, results):
            if result.success:
                print(f"{route['origin']}->{route['destination']}: {result.best_flight}")
    """
    if not _AGENT_API_AVAILABLE:
        raise ImportError(
            "Async API requires pydantic. Install with: pip install fast-flights[agent]"
        )
    
    if max_concurrent:
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def search_with_semaphore(route: Dict[str, Any]) -> FlightSearchResult:
            async with semaphore:
                return await search_flights_async(route, fetch_mode=fetch_mode)
        
        tasks = [search_with_semaphore(route) for route in routes]
    else:
        tasks = [
            search_flights_async(route, fetch_mode=fetch_mode) 
            for route in routes
        ]
    
    return await asyncio.gather(*tasks)


async def search_date_range(
    origin: str,
    destination: str,
    start_date: str,
    end_date: str,
    adults: int = 1,
    seat_class: str = "economy",
    fetch_mode: Optional[str] = None,
    max_concurrent: int = 5,
) -> Dict[str, Any]:
    """
    Search flights across a range of dates concurrently.
    
    Useful for finding the cheapest day to fly within a date range.
    
    Args:
        origin: Origin airport IATA code.
        destination: Destination airport IATA code.
        start_date: Start of date range (YYYY-MM-DD).
        end_date: End of date range (YYYY-MM-DD).
        adults: Number of adult passengers.
        seat_class: Seat class preference.
        fetch_mode: Override the default fetch mode.
        max_concurrent: Maximum concurrent searches (default: 5).
        
    Returns:
        Dictionary containing:
            - dates: Dict of date -> FlightSearchResult
            - cheapest_date: Date with lowest price
            - cheapest_price: Lowest price found
            - price_range: (min_price, max_price)
            - successful_searches: Number of successful searches
            - failed_searches: Number of failed searches
            
    Example:
        result = await search_date_range(
            origin="JFK",
            destination="LAX",
            start_date="2025-06-01",
            end_date="2025-06-07"
        )
        print(f"Cheapest: {result['cheapest_date']} at {result['cheapest_price']}")
    """
    from datetime import datetime, timedelta
    
    if not _AGENT_API_AVAILABLE:
        raise ImportError(
            "Async API requires pydantic. Install with: pip install fast-flights[agent]"
        )
    
    # Generate date list
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    # Build routes
    routes = [
        {
            "origin": origin,
            "destination": destination,
            "departure_date": date,
            "adults": adults,
            "seat_class": seat_class,
        }
        for date in dates
    ]
    
    # Search concurrently
    results = await search_multiple_routes(
        routes, 
        fetch_mode=fetch_mode, 
        max_concurrent=max_concurrent
    )
    
    # Analyze results
    date_results = dict(zip(dates, results))
    successful = [(d, r) for d, r in date_results.items() if r.success and r.best_flight]
    failed = [d for d, r in date_results.items() if not r.success]
    
    # Find cheapest
    cheapest_date = None
    cheapest_price = None
    prices = []
    
    for date, result in successful:
        if result.best_flight and result.best_flight.get("price"):
            # Extract numeric price
            price_str = result.best_flight["price"]
            try:
                # Remove currency symbols and parse
                price = float("".join(c for c in price_str if c.isdigit() or c == "."))
                prices.append(price)
                if cheapest_price is None or price < cheapest_price:
                    cheapest_price = price
                    cheapest_date = date
            except (ValueError, TypeError):
                pass
    
    return {
        "dates": date_results,
        "cheapest_date": cheapest_date,
        "cheapest_price": f"${cheapest_price:.0f}" if cheapest_price else None,
        "price_range": (f"${min(prices):.0f}", f"${max(prices):.0f}") if prices else None,
        "successful_searches": len(successful),
        "failed_searches": len(failed),
        "total_dates": len(dates),
    }


__all__ = [
    # Core async functions
    "search_flights_async",
    "search_airports_async",
    "compare_flight_dates_async",
    # Multi-route functions
    "search_multiple_routes",
    "search_date_range",
    # Utilities
    "run_in_executor",
    "get_executor",
    "shutdown_executor",
]
