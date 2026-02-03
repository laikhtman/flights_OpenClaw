from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .types import PriceLevel


@dataclass
class Result:
    """Flight search result containing price level and flight list."""
    current_price: PriceLevel
    flights: List[Flight]


@dataclass
class Flight:
    """A single flight option from search results."""
    is_best: bool
    name: str
    departure: str
    arrival: str
    arrival_time_ahead: str
    duration: str
    stops: int
    delay: Optional[str]
    price: str
