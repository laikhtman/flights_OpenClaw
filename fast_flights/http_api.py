"""
FastAPI HTTP Server for fast-flights.

Provides a REST API for flight search, airport lookup, date comparison,
price tracking, and airline filtering.

Run with:
    uvicorn fast_flights.http_api:app --reload

Or using the CLI:
    fast-flights-api

Environment Variables:
    FAST_FLIGHTS_API_KEY: API key for authentication (optional)
    FAST_FLIGHTS_RATE_LIMIT: Requests per minute (default: 60)
    FAST_FLIGHTS_CORS_ORIGINS: Comma-separated CORS origins (default: *)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

try:
    from fastapi import FastAPI, HTTPException, Request, Depends, Security, Query, Body
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from fastapi.security import APIKeyHeader
    from pydantic import BaseModel, Field
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    raise ImportError(
        "FastAPI not installed. Install with: pip install fast-flights[api]"
    )

# Import our APIs
from .agent_api import search_flights, search_airports, compare_flight_dates
from .schema_v2 import FlightSearchRequest, FlightSearchResult, PYDANTIC_AVAILABLE

# Optional imports
try:
    from .price_tracker import get_price_tracker
    from .price_storage import get_price_storage
    PRICE_TRACKING_AVAILABLE = True
except ImportError:
    PRICE_TRACKING_AVAILABLE = False

try:
    from .flexible_dates import (
        search_flexible_dates,
        search_weekend_flights,
        search_weekday_flights,
        get_calendar_heatmap,
        suggest_best_dates,
    )
    FLEX_DATES_AVAILABLE = True
except ImportError:
    FLEX_DATES_AVAILABLE = False

try:
    from .airline_filter import (
        get_airline_info,
        get_airlines_by_alliance,
        search_airlines as search_airlines_func,
        apply_airline_filters,
        get_low_cost_carriers,
        Alliance,
    )
    AIRLINE_FILTER_AVAILABLE = True
except ImportError:
    AIRLINE_FILTER_AVAILABLE = False

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

API_KEY = os.getenv("FAST_FLIGHTS_API_KEY")
RATE_LIMIT = int(os.getenv("FAST_FLIGHTS_RATE_LIMIT", "60"))
CORS_ORIGINS = os.getenv("FAST_FLIGHTS_CORS_ORIGINS", "*").split(",")

# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimitMiddleware:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if a request is allowed."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[client_id] = [
            t for t in self.requests[client_id] if t > minute_ago
        ]
        
        # Check limit
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False
        
        # Record request
        self.requests[client_id].append(now)
        return True
    
    def get_remaining(self, client_id: str) -> int:
        """Get remaining requests for this minute."""
        now = time.time()
        minute_ago = now - 60
        
        self.requests[client_id] = [
            t for t in self.requests[client_id] if t > minute_ago
        ]
        
        return max(0, self.requests_per_minute - len(self.requests[client_id]))


rate_limiter = RateLimitMiddleware(RATE_LIMIT)

# ============================================================================
# Request/Response Models
# ============================================================================

class FlightSearchRequestModel(BaseModel):
    """Request model for flight search."""
    origin: str = Field(..., min_length=3, max_length=4, description="Origin airport IATA code")
    destination: str = Field(..., min_length=3, max_length=4, description="Destination airport IATA code")
    departure_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Departure date (YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Return date for round-trip")
    adults: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    children: int = Field(0, ge=0, le=8, description="Number of child passengers")
    seat_class: str = Field("economy", description="Seat class")
    max_stops: Optional[int] = Field(None, ge=0, le=2, description="Maximum number of stops")

    class Config:
        json_schema_extra = {
            "example": {
                "origin": "JFK",
                "destination": "LAX",
                "departure_date": "2025-06-15",
                "adults": 2,
                "seat_class": "economy"
            }
        }


class DateCompareRequestModel(BaseModel):
    """Request model for date comparison."""
    origin: str = Field(..., min_length=3, max_length=4)
    destination: str = Field(..., min_length=3, max_length=4)
    dates: List[str] = Field(..., min_length=2, max_length=7)
    adults: int = Field(1, ge=1, le=9)
    seat_class: str = Field("economy")


class FlexibleSearchRequestModel(BaseModel):
    """Request model for flexible date search."""
    origin: str = Field(..., min_length=3, max_length=4)
    destination: str = Field(..., min_length=3, max_length=4)
    departure_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    days_before: int = Field(3, ge=0, le=7)
    days_after: int = Field(3, ge=0, le=7)
    return_date: Optional[str] = None
    seat_class: str = Field("economy")
    adults: int = Field(1, ge=1, le=9)


class CalendarHeatmapRequestModel(BaseModel):
    """Request model for calendar heatmap."""
    origin: str = Field(..., min_length=3, max_length=4)
    destination: str = Field(..., min_length=3, max_length=4)
    year: int = Field(..., ge=2024, le=2030)
    month: int = Field(..., ge=1, le=12)
    seat_class: str = Field("economy")
    adults: int = Field(1, ge=1, le=9)
    sample_days: Optional[List[int]] = None


class PriceAlertRequestModel(BaseModel):
    """Request model for price alert."""
    origin: str = Field(..., min_length=3, max_length=4)
    destination: str = Field(..., min_length=3, max_length=4)
    departure_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    target_price: float = Field(..., gt=0)
    return_date: Optional[str] = None
    webhook_url: Optional[str] = None
    email: Optional[str] = None


class AirlineFilterRequestModel(BaseModel):
    """Request model for airline filtering."""
    flights: List[Dict[str, Any]]
    include_airlines: Optional[List[str]] = None
    exclude_airlines: Optional[List[str]] = None
    alliances: Optional[List[str]] = None
    exclude_alliances: Optional[List[str]] = None
    include_low_cost: bool = True
    only_low_cost: bool = False
    wide_body_only: bool = False
    exclude_regional: bool = False
    preferred_airlines: Optional[List[str]] = None
    loyalty_program: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: str
    features: Dict[str, bool]


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    suggestion: Optional[str] = None


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Fast Flights API",
    description="""
🛫 **Fast Flights API** - A powerful flight search API powered by Google Flights data.

## Features

- ✈️ **Flight Search** - Search flights with detailed pricing and schedules
- 🔍 **Airport Lookup** - Find airport codes by name or city
- 📅 **Date Comparison** - Compare prices across multiple dates
- 🗓️ **Flexible Dates** - Search +/- N days around your preferred date
- 📈 **Price Tracking** - Track prices and set alerts
- ✈️ **Airline Filtering** - Filter by airline, alliance, aircraft type

## Authentication

Set the `X-API-Key` header if authentication is enabled.

## Rate Limiting

Default: 60 requests per minute per IP address.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ============================================================================
# Dependencies
# ============================================================================

async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """Verify API key if authentication is enabled."""
    if not API_KEY:
        return None  # No auth required
    
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Set X-API-Key header."
        )
    
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )
    
    return api_key


async def check_rate_limit(request: Request) -> None:
    """Check rate limit for the request."""
    client_ip = request.client.host if request.client else "unknown"
    
    if not rate_limiter.is_allowed(client_ip):
        remaining = rate_limiter.get_remaining(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in 60 seconds.",
            headers={"X-RateLimit-Remaining": str(remaining)}
        )


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", include_in_schema=False)
async def root():
    """Root redirect to docs."""
    return {"message": "Fast Flights API", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        features={
            "flight_search": True,
            "airport_lookup": True,
            "date_comparison": True,
            "flexible_dates": FLEX_DATES_AVAILABLE,
            "price_tracking": PRICE_TRACKING_AVAILABLE,
            "airline_filtering": AIRLINE_FILTER_AVAILABLE,
        }
    )


@app.post("/search", tags=["Flights"], dependencies=[Depends(check_rate_limit)])
async def search_flights_endpoint(
    request: FlightSearchRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Search for flights between airports.
    
    Returns available flights with prices, times, stops, and duration.
    The `current_price` field indicates if prices are low, typical, or high.
    """
    try:
        result = search_flights({
            "origin": request.origin.upper(),
            "destination": request.destination.upper(),
            "departure_date": request.departure_date,
            "return_date": request.return_date,
            "adults": request.adults,
            "children": request.children,
            "seat_class": request.seat_class,
            "max_stops": request.max_stops,
        })
        
        response = result.to_agent_response()
        response["summary"] = result.summary()
        return response
        
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/airports", tags=["Airports"], dependencies=[Depends(check_rate_limit)])
async def search_airports_endpoint(
    query: str = Query(..., min_length=2, description="City or airport name to search"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Search for airports by name or city.
    
    Returns matching airports with their IATA codes.
    """
    try:
        airports = search_airports(query, limit=limit)
        return {
            "query": query,
            "results": airports,
            "total": len(airports),
            "hint": "Use the 'code' field as origin/destination in /search"
        }
    except Exception as e:
        logger.error(f"Airport search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare", tags=["Flights"], dependencies=[Depends(check_rate_limit)])
async def compare_dates_endpoint(
    request: DateCompareRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Compare flight prices across multiple dates.
    
    Helps find the cheapest day to fly.
    """
    try:
        result = compare_flight_dates(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            dates=request.dates,
            adults=request.adults,
            seat_class=request.seat_class,
        )
        return result
    except Exception as e:
        logger.error(f"Compare error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Flexible Date Endpoints
# ============================================================================

@app.post("/flexible-search", tags=["Flexible Dates"], dependencies=[Depends(check_rate_limit)])
async def flexible_search_endpoint(
    request: FlexibleSearchRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Search for flights with flexible dates (+/- N days).
    
    Finds the cheapest days within your date range.
    """
    if not FLEX_DATES_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Flexible dates not available. Install with: pip install fast-flights[agent]"
        )
    
    try:
        result = search_flexible_dates(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            departure_date=request.departure_date,
            days_before=request.days_before,
            days_after=request.days_after,
            return_date=request.return_date,
            seat_class=request.seat_class,
            adults=request.adults,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Flexible search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/weekend-flights", tags=["Flexible Dates"], dependencies=[Depends(check_rate_limit)])
async def weekend_flights_endpoint(
    origin: str = Query(..., min_length=3, max_length=4),
    destination: str = Query(..., min_length=3, max_length=4),
    start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    num_weekends: int = Query(4, ge=1, le=8),
    seat_class: str = Query("economy"),
    adults: int = Query(1, ge=1, le=9),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Search for weekend-only flights.
    
    Returns prices for Saturdays and Sundays.
    """
    if not FLEX_DATES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Flexible dates not available")
    
    try:
        result = search_weekend_flights(
            origin=origin.upper(),
            destination=destination.upper(),
            start_date=start_date,
            num_weekends=num_weekends,
            seat_class=seat_class,
            adults=adults,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Weekend search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/calendar-heatmap", tags=["Flexible Dates"], dependencies=[Depends(check_rate_limit)])
async def calendar_heatmap_endpoint(
    request: CalendarHeatmapRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get a monthly calendar heatmap of flight prices.
    
    Shows prices for each day with the cheapest day highlighted.
    """
    if not FLEX_DATES_AVAILABLE:
        raise HTTPException(status_code=501, detail="Flexible dates not available")
    
    try:
        result = get_calendar_heatmap(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            year=request.year,
            month=request.month,
            seat_class=request.seat_class,
            adults=request.adults,
            sample_days=request.sample_days,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Calendar heatmap error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Price Tracking Endpoints
# ============================================================================

@app.post("/track", tags=["Price Tracking"], dependencies=[Depends(check_rate_limit)])
async def track_price_endpoint(
    origin: str = Query(..., min_length=3, max_length=4),
    destination: str = Query(..., min_length=3, max_length=4),
    departure_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    return_date: Optional[str] = Query(None),
    seat_class: str = Query("economy"),
    check_interval_minutes: int = Query(60, ge=15, le=1440),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Start tracking a route for price changes.
    
    Monitors prices and records history.
    """
    if not PRICE_TRACKING_AVAILABLE:
        raise HTTPException(status_code=501, detail="Price tracking not available")
    
    try:
        tracker = get_price_tracker()
        route_id = tracker.track_route(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            seat_class=seat_class,
            check_interval_minutes=check_interval_minutes,
        )
        
        # Immediate price check
        record = tracker.check_price(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            seat_class=seat_class,
        )
        
        return {
            "status": "success",
            "route_id": route_id,
            "route": f"{origin.upper()} → {destination.upper()}",
            "departure_date": departure_date,
            "current_price": record.price if record else None,
            "check_interval_minutes": check_interval_minutes,
        }
    except Exception as e:
        logger.error(f"Track price error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/price-history", tags=["Price Tracking"], dependencies=[Depends(check_rate_limit)])
async def price_history_endpoint(
    origin: str = Query(..., min_length=3, max_length=4),
    destination: str = Query(..., min_length=3, max_length=4),
    departure_date: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get historical prices for a route.
    
    Returns price records and statistics.
    """
    if not PRICE_TRACKING_AVAILABLE:
        raise HTTPException(status_code=501, detail="Price tracking not available")
    
    try:
        tracker = get_price_tracker()
        history = tracker.get_price_history(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            days=days,
        )
        stats = tracker.get_price_stats(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            days=days,
        )
        
        return {
            "route": f"{origin.upper()} → {destination.upper()}",
            "departure_date": departure_date or "all dates",
            "days_analyzed": days,
            "statistics": stats,
            "price_history": [
                {
                    "price": r.price,
                    "price_level": r.price_level,
                    "airline": r.airline,
                    "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                }
                for r in history[:50]  # Limit response size
            ],
            "total_records": len(history),
        }
    except Exception as e:
        logger.error(f"Price history error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/alerts", tags=["Price Tracking"], dependencies=[Depends(check_rate_limit)])
async def set_alert_endpoint(
    request: PriceAlertRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Set a price alert for a route.
    
    Get notified when price drops below target.
    """
    if not PRICE_TRACKING_AVAILABLE:
        raise HTTPException(status_code=501, detail="Price tracking not available")
    
    try:
        tracker = get_price_tracker()
        alert_id = tracker.set_alert(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            departure_date=request.departure_date,
            target_price=request.target_price,
            return_date=request.return_date,
            webhook_url=request.webhook_url,
            email=request.email,
        )
        
        # Check current price
        record = tracker.check_price(
            origin=request.origin.upper(),
            destination=request.destination.upper(),
            departure_date=request.departure_date,
            return_date=request.return_date,
        )
        
        return {
            "status": "success",
            "alert_id": alert_id,
            "route": f"{request.origin.upper()} → {request.destination.upper()}",
            "target_price": request.target_price,
            "current_price": record.price if record else None,
            "will_trigger": (record.price <= request.target_price) if record and record.price else None,
        }
    except Exception as e:
        logger.error(f"Set alert error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tracked-routes", tags=["Price Tracking"], dependencies=[Depends(check_rate_limit)])
async def tracked_routes_endpoint(
    active_only: bool = Query(True),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """List all tracked routes."""
    if not PRICE_TRACKING_AVAILABLE:
        raise HTTPException(status_code=501, detail="Price tracking not available")
    
    try:
        tracker = get_price_tracker()
        routes = tracker.get_tracked_routes(active_only=active_only)
        
        return {
            "total": len(routes),
            "routes": [
                {
                    "id": r.id,
                    "route": f"{r.origin} → {r.destination}",
                    "departure_date": r.departure_date,
                    "is_active": r.is_active,
                    "last_price": r.last_price,
                    "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                }
                for r in routes
            ],
        }
    except Exception as e:
        logger.error(f"Tracked routes error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Airline Filtering Endpoints
# ============================================================================

@app.get("/airlines/search", tags=["Airlines"], dependencies=[Depends(check_rate_limit)])
async def search_airlines_endpoint(
    query: str = Query(..., min_length=1, description="Airline name or code"),
    limit: int = Query(10, ge=1, le=50),
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Search for airline information.
    
    Find airline codes, alliances, and frequent flyer programs.
    """
    if not AIRLINE_FILTER_AVAILABLE:
        raise HTTPException(status_code=501, detail="Airline filtering not available")
    
    try:
        results = search_airlines_func(query, limit=limit)
        return {
            "query": query,
            "total": len(results),
            "airlines": [a.to_dict() for a in results],
        }
    except Exception as e:
        logger.error(f"Airline search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/airlines/{code}", tags=["Airlines"], dependencies=[Depends(check_rate_limit)])
async def get_airline_endpoint(
    code: str,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get detailed information about an airline.
    
    Returns alliance, country, and frequent flyer program.
    """
    if not AIRLINE_FILTER_AVAILABLE:
        raise HTTPException(status_code=501, detail="Airline filtering not available")
    
    try:
        info = get_airline_info(code.upper())
        if not info:
            raise HTTPException(status_code=404, detail=f"Airline not found: {code}")
        
        return info.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get airline error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alliances/{alliance}", tags=["Airlines"], dependencies=[Depends(check_rate_limit)])
async def get_alliance_endpoint(
    alliance: str,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Get all airlines in an alliance.
    
    Alliances: star_alliance, oneworld, skyteam
    """
    if not AIRLINE_FILTER_AVAILABLE:
        raise HTTPException(status_code=501, detail="Airline filtering not available")
    
    try:
        alliance_enum = Alliance(alliance.lower())
        airlines = get_airlines_by_alliance(alliance_enum)
        
        return {
            "alliance": alliance,
            "total": len(airlines),
            "airlines": [a.to_dict() for a in airlines],
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid alliance: {alliance}. Use: star_alliance, oneworld, skyteam"
        )
    except Exception as e:
        logger.error(f"Get alliance error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/airlines/low-cost/list", tags=["Airlines"], dependencies=[Depends(check_rate_limit)])
async def low_cost_carriers_endpoint(
    api_key: Optional[str] = Depends(verify_api_key),
):
    """Get list of low-cost/budget airlines."""
    if not AIRLINE_FILTER_AVAILABLE:
        raise HTTPException(status_code=501, detail="Airline filtering not available")
    
    try:
        carriers = get_low_cost_carriers()
        return {
            "total": len(carriers),
            "carriers": [c.to_dict() for c in carriers],
        }
    except Exception as e:
        logger.error(f"Low cost carriers error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/filter-flights", tags=["Airlines"], dependencies=[Depends(check_rate_limit)])
async def filter_flights_endpoint(
    request: AirlineFilterRequestModel,
    api_key: Optional[str] = Depends(verify_api_key),
):
    """
    Filter flight results by airline preferences.
    
    Apply filters for airlines, alliances, aircraft types, and more.
    """
    if not AIRLINE_FILTER_AVAILABLE:
        raise HTTPException(status_code=501, detail="Airline filtering not available")
    
    try:
        result = apply_airline_filters(
            flights=request.flights,
            include_airlines=request.include_airlines,
            exclude_airlines=request.exclude_airlines,
            alliances=request.alliances,
            exclude_alliances=request.exclude_alliances,
            include_low_cost=request.include_low_cost,
            only_low_cost=request.only_low_cost,
            wide_body_only=request.wide_body_only,
            exclude_regional=request.exclude_regional,
            preferred_airlines=request.preferred_airlines,
            loyalty_program=request.loyalty_program,
        )
        return result.to_dict()
    except Exception as e:
        logger.error(f"Filter flights error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG") else None,
        },
    )


# ============================================================================
# CLI Entry Point
# ============================================================================

def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the FastAPI server."""
    import uvicorn
    
    logger.info(f"Starting Fast Flights API on http://{host}:{port}")
    logger.info(f"API Docs: http://{host}:{port}/docs")
    
    uvicorn.run(
        "fast_flights.http_api:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    host = sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    
    run(host=host, port=port, reload=True)
