"""
Flexible date search module for finding optimal flight dates.

Provides date range queries, weekend searches, weekday filtering,
calendar heatmaps, and smart date suggestions.
"""

import calendar
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore

# Import agent API for searches
try:
    from .agent_api import search_flights
    from .schema_v2 import FlightSearchResult
    AGENT_API_AVAILABLE = True
except ImportError:
    AGENT_API_AVAILABLE = False


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class DatePrice:
    """Price information for a specific date."""
    date: str  # YYYY-MM-DD
    price: Optional[float] = None
    price_level: Optional[str] = None  # low, typical, high
    airline: Optional[str] = None
    is_weekend: bool = False
    day_of_week: str = ""  # Monday, Tuesday, etc.
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "price": self.price,
            "price_level": self.price_level,
            "airline": self.airline,
            "is_weekend": self.is_weekend,
            "day_of_week": self.day_of_week,
            "error": self.error,
        }


@dataclass
class FlexibleSearchResult:
    """Result of a flexible date search."""
    origin: str
    destination: str
    base_date: str
    dates_searched: int
    results: List[DatePrice] = field(default_factory=list)
    cheapest_date: Optional[DatePrice] = None
    most_expensive_date: Optional[DatePrice] = None
    average_price: Optional[float] = None
    recommendation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "base_date": self.base_date,
            "dates_searched": self.dates_searched,
            "results": [r.to_dict() for r in self.results],
            "cheapest_date": self.cheapest_date.to_dict() if self.cheapest_date else None,
            "most_expensive_date": self.most_expensive_date.to_dict() if self.most_expensive_date else None,
            "average_price": self.average_price,
            "recommendation": self.recommendation,
        }


@dataclass
class CalendarHeatmap:
    """Monthly calendar with price data."""
    origin: str
    destination: str
    year: int
    month: int
    month_name: str
    days: List[DatePrice] = field(default_factory=list)
    cheapest_day: Optional[DatePrice] = None
    cheapest_week: Optional[int] = None  # Week number (1-5)
    price_range: Tuple[Optional[float], Optional[float]] = (None, None)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "year": self.year,
            "month": self.month,
            "month_name": self.month_name,
            "days": [d.to_dict() for d in self.days],
            "cheapest_day": self.cheapest_day.to_dict() if self.cheapest_day else None,
            "cheapest_week": self.cheapest_week,
            "price_range": {
                "min": self.price_range[0],
                "max": self.price_range[1],
            },
        }


# ============================================================================
# Date Utilities
# ============================================================================

def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def format_date(dt: datetime) -> str:
    """Format a datetime to YYYY-MM-DD string."""
    return dt.strftime("%Y-%m-%d")


def get_day_info(date_str: str) -> Tuple[str, bool]:
    """Get day of week name and whether it's a weekend."""
    dt = parse_date(date_str)
    day_name = dt.strftime("%A")
    is_weekend = dt.weekday() >= 5  # Saturday = 5, Sunday = 6
    return day_name, is_weekend


def generate_date_range(
    base_date: str,
    days_before: int = 0,
    days_after: int = 0,
) -> List[str]:
    """Generate a list of dates around a base date."""
    base = parse_date(base_date)
    dates = []
    
    for offset in range(-days_before, days_after + 1):
        dt = base + timedelta(days=offset)
        # Skip dates in the past
        if dt >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            dates.append(format_date(dt))
    
    return dates


def generate_weekend_dates(
    start_date: str,
    num_weekends: int = 4,
) -> List[str]:
    """Generate weekend dates (Saturdays and Sundays) from a start date."""
    start = parse_date(start_date)
    dates = []
    current = start
    weekends_found = 0
    
    # Find up to num_weekends worth of weekend days
    while weekends_found < num_weekends * 2 and len(dates) < 30:
        if current.weekday() >= 5:  # Weekend
            if current >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                dates.append(format_date(current))
                if current.weekday() == 6:  # Sunday
                    weekends_found += 1
        current += timedelta(days=1)
    
    return dates


def generate_weekday_dates(
    start_date: str,
    weekdays: List[int],  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    num_weeks: int = 4,
) -> List[str]:
    """Generate dates for specific weekdays."""
    start = parse_date(start_date)
    dates = []
    current = start
    weeks_covered = 0
    last_week = -1
    
    while weeks_covered < num_weeks and len(dates) < 30:
        if current.weekday() in weekdays:
            if current >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
                dates.append(format_date(current))
                
                # Track weeks
                current_week = current.isocalendar()[1]
                if current_week != last_week:
                    weeks_covered += 1
                    last_week = current_week
        
        current += timedelta(days=1)
    
    return dates


def generate_month_dates(year: int, month: int) -> List[str]:
    """Generate all dates in a month."""
    _, num_days = calendar.monthrange(year, month)
    dates = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for day in range(1, num_days + 1):
        dt = datetime(year, month, day)
        if dt >= today:
            dates.append(format_date(dt))
    
    return dates


# ============================================================================
# Price Fetching
# ============================================================================

def _fetch_price_for_date(
    origin: str,
    destination: str,
    date: str,
    return_date: Optional[str] = None,
    seat_class: str = "economy",
    adults: int = 1,
) -> DatePrice:
    """Fetch price for a single date."""
    if not AGENT_API_AVAILABLE:
        return DatePrice(
            date=date,
            error="Agent API not available",
            day_of_week=get_day_info(date)[0],
            is_weekend=get_day_info(date)[1],
        )
    
    try:
        result = search_flights({
            "origin": origin,
            "destination": destination,
            "departure_date": date,
            "return_date": return_date,
            "seat_class": seat_class,
            "adults": adults,
        })
        
        day_name, is_weekend = get_day_info(date)
        
        if result.success and result.flights:
            best = result.flights[0]
            price = _parse_price(best.price)
            return DatePrice(
                date=date,
                price=price,
                price_level=result.current_price,
                airline=best.name,
                is_weekend=is_weekend,
                day_of_week=day_name,
            )
        else:
            return DatePrice(
                date=date,
                error=result.error or "No flights found",
                is_weekend=is_weekend,
                day_of_week=day_name,
            )
    except Exception as e:
        day_name, is_weekend = get_day_info(date)
        return DatePrice(
            date=date,
            error=str(e),
            is_weekend=is_weekend,
            day_of_week=day_name,
        )


def _parse_price(price_str: str) -> float:
    """Parse price string to float."""
    match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
    return float(match.group()) if match else 0.0


def fetch_prices_parallel(
    origin: str,
    destination: str,
    dates: List[str],
    return_date: Optional[str] = None,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[DatePrice]:
    """Fetch prices for multiple dates in parallel."""
    results: List[DatePrice] = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_date = {
            executor.submit(
                _fetch_price_for_date,
                origin, destination, date, return_date, seat_class, adults
            ): date
            for date in dates
        }
        
        completed = 0
        for future in as_completed(future_to_date):
            result = future.result()
            results.append(result)
            completed += 1
            
            if on_progress:
                on_progress(completed, len(dates))
    
    # Sort by date
    results.sort(key=lambda x: x.date)
    return results


# ============================================================================
# Flexible Search Functions
# ============================================================================

def search_flexible_dates(
    origin: str,
    destination: str,
    departure_date: str,
    days_before: int = 3,
    days_after: int = 3,
    return_date: Optional[str] = None,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
) -> FlexibleSearchResult:
    """
    Search for flights within a flexible date range.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        departure_date: Center date for the search (YYYY-MM-DD)
        days_before: Number of days before the base date to search
        days_after: Number of days after the base date to search
        return_date: Return date for round-trip (optional)
        seat_class: Seat class
        adults: Number of adults
        max_workers: Maximum parallel requests
        
    Returns:
        FlexibleSearchResult with prices for each date
        
    Example:
        >>> result = search_flexible_dates("JFK", "LAX", "2025-06-15", days_before=3, days_after=3)
        >>> print(f"Cheapest: {result.cheapest_date.date} at ${result.cheapest_date.price}")
    """
    dates = generate_date_range(departure_date, days_before, days_after)
    
    results = fetch_prices_parallel(
        origin=origin.upper(),
        destination=destination.upper(),
        dates=dates,
        return_date=return_date,
        seat_class=seat_class,
        adults=adults,
        max_workers=max_workers,
    )
    
    return _build_flexible_result(
        origin=origin.upper(),
        destination=destination.upper(),
        base_date=departure_date,
        results=results,
    )


def search_weekend_flights(
    origin: str,
    destination: str,
    start_date: str,
    num_weekends: int = 4,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
) -> FlexibleSearchResult:
    """
    Search for flights on weekends only.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        start_date: Start searching from this date
        num_weekends: Number of weekends to search
        seat_class: Seat class
        adults: Number of adults
        max_workers: Maximum parallel requests
        
    Returns:
        FlexibleSearchResult with weekend prices
    """
    dates = generate_weekend_dates(start_date, num_weekends)
    
    results = fetch_prices_parallel(
        origin=origin.upper(),
        destination=destination.upper(),
        dates=dates,
        seat_class=seat_class,
        adults=adults,
        max_workers=max_workers,
    )
    
    return _build_flexible_result(
        origin=origin.upper(),
        destination=destination.upper(),
        base_date=start_date,
        results=results,
    )


def search_weekday_flights(
    origin: str,
    destination: str,
    start_date: str,
    weekdays: List[Union[int, str]],
    num_weeks: int = 4,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
) -> FlexibleSearchResult:
    """
    Search for flights on specific weekdays.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        start_date: Start searching from this date
        weekdays: Days to search. Can be integers (0=Monday) or names ("tuesday")
        num_weeks: Number of weeks to search
        seat_class: Seat class
        adults: Number of adults
        max_workers: Maximum parallel requests
        
    Returns:
        FlexibleSearchResult with weekday prices
    """
    # Convert weekday names to integers
    weekday_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3,
        "fri": 4, "sat": 5, "sun": 6,
    }
    
    weekday_ints = []
    for wd in weekdays:
        if isinstance(wd, int):
            weekday_ints.append(wd)
        elif isinstance(wd, str):
            wd_lower = wd.lower()
            if wd_lower in weekday_map:
                weekday_ints.append(weekday_map[wd_lower])
    
    dates = generate_weekday_dates(start_date, weekday_ints, num_weeks)
    
    results = fetch_prices_parallel(
        origin=origin.upper(),
        destination=destination.upper(),
        dates=dates,
        seat_class=seat_class,
        adults=adults,
        max_workers=max_workers,
    )
    
    return _build_flexible_result(
        origin=origin.upper(),
        destination=destination.upper(),
        base_date=start_date,
        results=results,
    )


def get_calendar_heatmap(
    origin: str,
    destination: str,
    year: int,
    month: int,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
    sample_days: Optional[List[int]] = None,
) -> CalendarHeatmap:
    """
    Get a calendar heatmap of prices for a month.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        year: Year (e.g., 2025)
        month: Month (1-12)
        seat_class: Seat class
        adults: Number of adults
        max_workers: Maximum parallel requests
        sample_days: Specific days to sample (default: all days)
        
    Returns:
        CalendarHeatmap with daily prices
        
    Example:
        >>> heatmap = get_calendar_heatmap("JFK", "LAX", 2025, 6)
        >>> print(f"Cheapest day: {heatmap.cheapest_day.date}")
    """
    all_dates = generate_month_dates(year, month)
    
    # If sampling specific days, filter
    if sample_days:
        dates = [d for d in all_dates if parse_date(d).day in sample_days]
    else:
        dates = all_dates
    
    results = fetch_prices_parallel(
        origin=origin.upper(),
        destination=destination.upper(),
        dates=dates,
        seat_class=seat_class,
        adults=adults,
        max_workers=max_workers,
    )
    
    # Find cheapest and price range
    valid_results = [r for r in results if r.price is not None]
    cheapest = min(valid_results, key=lambda x: x.price) if valid_results else None
    
    prices = [r.price for r in valid_results if r.price]
    price_range = (min(prices), max(prices)) if prices else (None, None)
    
    # Find cheapest week
    cheapest_week = None
    if cheapest:
        cheapest_dt = parse_date(cheapest.date)
        # Week of month (1-5)
        cheapest_week = (cheapest_dt.day - 1) // 7 + 1
    
    return CalendarHeatmap(
        origin=origin.upper(),
        destination=destination.upper(),
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        days=results,
        cheapest_day=cheapest,
        cheapest_week=cheapest_week,
        price_range=price_range,
    )


def suggest_best_dates(
    origin: str,
    destination: str,
    preferred_date: str,
    flexibility_days: int = 7,
    prefer_weekends: bool = False,
    avoid_weekends: bool = False,
    max_results: int = 5,
    seat_class: str = "economy",
    adults: int = 1,
    max_workers: int = 3,
) -> FlexibleSearchResult:
    """
    Get smart suggestions for the best dates to fly.
    
    Args:
        origin: Origin airport code
        destination: Destination airport code
        preferred_date: Preferred departure date (YYYY-MM-DD)
        flexibility_days: How many days flexible (+/- from preferred)
        prefer_weekends: Only suggest weekend dates
        avoid_weekends: Exclude weekend dates
        max_results: Maximum number of suggestions to return
        seat_class: Seat class
        adults: Number of adults
        max_workers: Maximum parallel requests
        
    Returns:
        FlexibleSearchResult with top suggestions sorted by price
    """
    # Generate dates based on preferences
    if prefer_weekends:
        dates = generate_weekend_dates(preferred_date, num_weekends=flexibility_days // 3 + 1)
    else:
        dates = generate_date_range(preferred_date, flexibility_days, flexibility_days)
    
    # Filter out weekends if avoiding them
    if avoid_weekends:
        dates = [d for d in dates if not get_day_info(d)[1]]
    
    # Limit dates to search
    dates = dates[:min(len(dates), 14)]
    
    results = fetch_prices_parallel(
        origin=origin.upper(),
        destination=destination.upper(),
        dates=dates,
        seat_class=seat_class,
        adults=adults,
        max_workers=max_workers,
    )
    
    # Sort by price and take top results
    valid_results = [r for r in results if r.price is not None]
    valid_results.sort(key=lambda x: x.price or float('inf'))
    top_results = valid_results[:max_results]
    
    result = _build_flexible_result(
        origin=origin.upper(),
        destination=destination.upper(),
        base_date=preferred_date,
        results=top_results,
    )
    
    # Update recommendation
    if top_results:
        savings = None
        if len(valid_results) >= 2:
            # Calculate potential savings vs worst date
            worst_price = max(r.price for r in valid_results if r.price)
            best_price = top_results[0].price
            if worst_price and best_price:
                savings = worst_price - best_price
        
        result.recommendation = (
            f"Best date: {top_results[0].date} ({top_results[0].day_of_week}) "
            f"at ${top_results[0].price:.0f}"
        )
        if savings and savings > 0:
            result.recommendation += f" - Save ${savings:.0f} vs worst date!"
    
    return result


# ============================================================================
# Helper Functions
# ============================================================================

def _build_flexible_result(
    origin: str,
    destination: str,
    base_date: str,
    results: List[DatePrice],
) -> FlexibleSearchResult:
    """Build a FlexibleSearchResult from price results."""
    valid_results = [r for r in results if r.price is not None]
    
    cheapest = min(valid_results, key=lambda x: x.price) if valid_results else None
    most_expensive = max(valid_results, key=lambda x: x.price) if valid_results else None
    
    prices = [r.price for r in valid_results if r.price]
    avg_price = sum(prices) / len(prices) if prices else None
    
    # Build recommendation
    recommendation = ""
    if cheapest and most_expensive and cheapest.price and most_expensive.price:
        savings = most_expensive.price - cheapest.price
        recommendation = (
            f"Fly on {cheapest.date} ({cheapest.day_of_week}) to save "
            f"${savings:.0f} compared to {most_expensive.date}"
        )
    elif cheapest:
        recommendation = f"Best price found: {cheapest.date} at ${cheapest.price:.0f}"
    
    return FlexibleSearchResult(
        origin=origin,
        destination=destination,
        base_date=base_date,
        dates_searched=len(results),
        results=results,
        cheapest_date=cheapest,
        most_expensive_date=most_expensive,
        average_price=round(avg_price, 2) if avg_price else None,
        recommendation=recommendation,
    )
