"""
Pydantic models for AI agent integration.

This module provides strongly-typed, JSON-serializable models for flight search
that are optimized for AI agent consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Union

from .types import SeatClass, TripType, PriceLevel

# Import base Flight/Result from schema.py (single source of truth)
from .schema import Flight, Result

# Re-export for backwards compatibility
__all_base__ = ["Flight", "Result"]

# Try to import Pydantic, fall back to dataclasses if not available
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore
    def Field(*args, **kwargs):  # type: ignore
        return kwargs.get('default', None)


# ============================================================================
# Pydantic models for AI agent integration
# ============================================================================

if PYDANTIC_AVAILABLE:
    class FlightSchema(BaseModel):
        """A single flight option with full validation."""
        
        is_best: bool = Field(
            description="Whether this is marked as the best flight option"
        )
        name: str = Field(
            description="Airline name(s) operating the flight (e.g., 'Delta', 'United, American')"
        )
        departure: str = Field(
            description="Departure time as string (e.g., '10:30 AM', '14:45')"
        )
        arrival: str = Field(
            description="Arrival time as string (e.g., '2:45 PM', '18:30')"
        )
        arrival_time_ahead: str = Field(
            default="",
            description="Days ahead for arrival if overnight (e.g., '+1', '+2')"
        )
        duration: str = Field(
            description="Total flight duration (e.g., '5h 15m', '2h 30m')"
        )
        stops: int = Field(
            ge=0,
            description="Number of stops (0 = nonstop, 1 = one stop, etc.)"
        )
        delay: Optional[str] = Field(
            default=None,
            description="Delay information if any (e.g., 'Delayed 30 min')"
        )
        price: str = Field(
            description="Price as string with currency (e.g., '$299', '€250')"
        )
        
        model_config = {
            "json_schema_extra": {
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
        }

        @classmethod
        def from_flight(cls, flight: Flight) -> "FlightSchema":
            """Convert a Flight dataclass to FlightSchema."""
            return cls(
                is_best=flight.is_best,
                name=flight.name,
                departure=flight.departure,
                arrival=flight.arrival,
                arrival_time_ahead=flight.arrival_time_ahead,
                duration=flight.duration,
                stops=flight.stops,
                delay=flight.delay,
                price=flight.price
            )


    class FlightSearchResult(BaseModel):
        """Result of a flight search, optimized for AI agent consumption."""
        
        success: bool = Field(
            description="Whether the search completed successfully"
        )
        current_price: Literal["low", "typical", "high", "unknown"] = Field(
            description="Current price level indicator from Google Flights"
        )
        flights: List[FlightSchema] = Field(
            default_factory=list,
            description="List of available flight options"
        )
        search_url: Optional[str] = Field(
            default=None,
            description="Google Flights URL for this search (for user reference)"
        )
        error: Optional[str] = Field(
            default=None,
            description="Error message if search failed"
        )
        
        model_config = {
            "json_schema_extra": {
                "example": {
                    "success": True,
                    "current_price": "low",
                    "flights": [
                        {
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
                    ],
                    "search_url": "https://www.google.com/travel/flights?tfs=...",
                    "error": None
                }
            }
        }
        
        def to_agent_response(self) -> dict:
            """
            Convert to a format optimized for AI agent consumption.
            
            Returns a structured dict with:
            - status: "success" or "error"
            - data: flight information
            - metadata: additional context
            """
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
        
        def summary(self) -> str:
            """
            Get a human-readable summary of the search results.
            
            Useful for AI agents to include in responses to users.
            """
            if not self.success:
                return f"Flight search failed: {self.error}"
            
            if not self.flights:
                return "No flights found for the specified route and dates."
            
            best = self.flights[0] if self.flights else None
            summary_parts = [
                f"Found {len(self.flights)} flight option(s).",
                f"Price level: {self.current_price}."
            ]
            
            if best:
                summary_parts.append(
                    f"Best option: {best.name} at {best.price}, "
                    f"{best.departure} → {best.arrival} ({best.duration}, "
                    f"{'nonstop' if best.stops == 0 else f'{best.stops} stop(s)'})."
                )
            
            return " ".join(summary_parts)


    class FlightSearchRequest(BaseModel):
        """
        Input schema for flight search - used by AI agents.
        
        This model validates and normalizes input parameters for flight searches.
        """
        
        origin: str = Field(
            description="Origin airport IATA code (e.g., 'JFK', 'LAX', 'ORD')",
            min_length=3,
            max_length=4
        )
        destination: str = Field(
            description="Destination airport IATA code (e.g., 'SFO', 'LHR', 'NRT')",
            min_length=3,
            max_length=4
        )
        departure_date: str = Field(
            description="Departure date in YYYY-MM-DD format (e.g., '2025-06-15')",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        )
        return_date: Optional[str] = Field(
            default=None,
            description="Return date for round-trip in YYYY-MM-DD format. Omit for one-way.",
            pattern=r"^\d{4}-\d{2}-\d{2}$"
        )
        adults: int = Field(
            default=1,
            ge=1,
            le=9,
            description="Number of adult passengers (1-9)"
        )
        children: int = Field(
            default=0,
            ge=0,
            le=8,
            description="Number of child passengers aged 2-11 (0-8)"
        )
        infants_in_seat: int = Field(
            default=0,
            ge=0,
            le=4,
            description="Number of infants with their own seat (0-4)"
        )
        infants_on_lap: int = Field(
            default=0,
            ge=0,
            le=4,
            description="Number of lap infants under 2 years (0-4)"
        )
        seat_class: Literal["economy", "premium-economy", "business", "first"] = Field(
            default="economy",
            description="Seat/cabin class"
        )
        max_stops: Optional[int] = Field(
            default=None,
            ge=0,
            le=2,
            description="Maximum number of stops (0=nonstop only, 1, 2, or None for any)"
        )
        
        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "origin": "JFK",
                        "destination": "LAX",
                        "departure_date": "2025-06-15",
                        "adults": 2,
                        "seat_class": "economy"
                    },
                    {
                        "origin": "SFO",
                        "destination": "LHR",
                        "departure_date": "2025-07-01",
                        "return_date": "2025-07-15",
                        "adults": 1,
                        "seat_class": "business",
                        "max_stops": 1
                    }
                ]
            }
        }
        
        @property
        def trip_type(self) -> Literal["one-way", "round-trip"]:
            """Determine trip type based on whether return_date is provided."""
            return "round-trip" if self.return_date else "one-way"
        
        @property
        def total_passengers(self) -> int:
            """Total number of passengers."""
            return self.adults + self.children + self.infants_in_seat + self.infants_on_lap
        
        def validate_passengers(self) -> None:
            """
            Validate passenger configuration.
            
            Raises:
                ValueError: If passenger configuration is invalid.
            """
            if self.total_passengers > 9:
                raise ValueError(f"Total passengers ({self.total_passengers}) exceeds maximum of 9")
            if self.infants_on_lap > self.adults:
                raise ValueError(
                    f"Number of lap infants ({self.infants_on_lap}) cannot exceed "
                    f"number of adults ({self.adults})"
                )

else:
    # Fallback when Pydantic is not installed
    FlightSchema = Flight  # type: ignore
    FlightSearchResult = Result  # type: ignore
    FlightSearchRequest = None  # type: ignore


__all__ = [
    # Original dataclasses
    "Result",
    "Flight",
    # Pydantic models
    "FlightSchema",
    "FlightSearchResult", 
    "FlightSearchRequest",
    # Availability flag
    "PYDANTIC_AVAILABLE",
]
