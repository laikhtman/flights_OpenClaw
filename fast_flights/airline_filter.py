"""
Airline filtering module for flight search results.

Provides airline preferences, alliance filtering, aircraft type filtering,
and loyalty program integration for prioritizing preferred carriers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore


# ============================================================================
# Airline Alliances
# ============================================================================

class Alliance(str, Enum):
    """Major airline alliances."""
    STAR_ALLIANCE = "star_alliance"
    ONEWORLD = "oneworld"
    SKYTEAM = "skyteam"
    NONE = "none"  # Not in any alliance


# Alliance member airlines (IATA codes)
STAR_ALLIANCE_MEMBERS: Set[str] = {
    "AC",  # Air Canada
    "CA",  # Air China
    "AI",  # Air India
    "NZ",  # Air New Zealand
    "NH",  # ANA (All Nippon Airways)
    "OZ",  # Asiana Airlines
    "OS",  # Austrian Airlines
    "AV",  # Avianca
    "SN",  # Brussels Airlines
    "CM",  # Copa Airlines
    "MS",  # EgyptAir
    "ET",  # Ethiopian Airlines
    "BR",  # EVA Air
    "LH",  # Lufthansa
    "LO",  # LOT Polish Airlines
    "SK",  # SAS Scandinavian Airlines
    "ZH",  # Shenzhen Airlines
    "SQ",  # Singapore Airlines
    "SA",  # South African Airways
    "LX",  # Swiss International Air Lines
    "TP",  # TAP Air Portugal
    "TG",  # Thai Airways
    "TK",  # Turkish Airlines
    "UA",  # United Airlines
}

ONEWORLD_MEMBERS: Set[str] = {
    "AA",  # American Airlines
    "BA",  # British Airways
    "CX",  # Cathay Pacific
    "AY",  # Finnair
    "IB",  # Iberia
    "JL",  # Japan Airlines
    "MH",  # Malaysia Airlines
    "QF",  # Qantas
    "QR",  # Qatar Airways
    "AT",  # Royal Air Maroc
    "RJ",  # Royal Jordanian
    "UL",  # SriLankan Airlines
    "FJ",  # Fiji Airways (oneworld connect)
    "AS",  # Alaska Airlines
}

SKYTEAM_MEMBERS: Set[str] = {
    "SU",  # Aeroflot
    "AR",  # Aerolíneas Argentinas
    "AM",  # Aeroméxico
    "AF",  # Air France
    "UX",  # Air Europa
    "CI",  # China Airlines
    "MU",  # China Eastern Airlines
    "CZ",  # China Southern Airlines
    "OK",  # Czech Airlines
    "DL",  # Delta Air Lines
    "GA",  # Garuda Indonesia
    "KE",  # Korean Air
    "KL",  # KLM Royal Dutch Airlines
    "ME",  # Middle East Airlines
    "SV",  # Saudia
    "RO",  # TAROM
    "VN",  # Vietnam Airlines
    "VS",  # Virgin Atlantic
    "MF",  # Xiamen Airlines
}

ALLIANCE_MAP: Dict[Alliance, Set[str]] = {
    Alliance.STAR_ALLIANCE: STAR_ALLIANCE_MEMBERS,
    Alliance.ONEWORLD: ONEWORLD_MEMBERS,
    Alliance.SKYTEAM: SKYTEAM_MEMBERS,
}


# ============================================================================
# Aircraft Types
# ============================================================================

class AircraftCategory(str, Enum):
    """Aircraft category classifications."""
    WIDE_BODY = "wide_body"
    NARROW_BODY = "narrow_body"
    REGIONAL = "regional"
    TURBOPROP = "turboprop"


# Common aircraft models by category
WIDE_BODY_AIRCRAFT: Set[str] = {
    # Boeing
    "747", "B747", "747-8", "747-400",
    "767", "B767", "767-300", "767-400",
    "777", "B777", "777-200", "777-300", "777-9", "777X",
    "787", "B787", "787-8", "787-9", "787-10", "Dreamliner",
    # Airbus
    "A330", "330", "A330-200", "A330-300", "A330-900", "A330neo",
    "A340", "340", "A340-300", "A340-600",
    "A350", "350", "A350-900", "A350-1000",
    "A380", "380",
}

NARROW_BODY_AIRCRAFT: Set[str] = {
    # Boeing
    "737", "B737", "737-700", "737-800", "737-900", "737 MAX", "737MAX",
    "757", "B757", "757-200", "757-300",
    # Airbus
    "A319", "319",
    "A320", "320", "A320neo",
    "A321", "321", "A321neo", "A321XLR",
}

REGIONAL_AIRCRAFT: Set[str] = {
    "CRJ", "CRJ-200", "CRJ-700", "CRJ-900",
    "ERJ", "E170", "E175", "E190", "E195", "E195-E2",
    "Embraer",
}

TURBOPROP_AIRCRAFT: Set[str] = {
    "ATR", "ATR 42", "ATR 72",
    "Dash 8", "Q400", "DHC-8",
    "Saab 340", "Saab 2000",
}

AIRCRAFT_CATEGORY_MAP: Dict[AircraftCategory, Set[str]] = {
    AircraftCategory.WIDE_BODY: WIDE_BODY_AIRCRAFT,
    AircraftCategory.NARROW_BODY: NARROW_BODY_AIRCRAFT,
    AircraftCategory.REGIONAL: REGIONAL_AIRCRAFT,
    AircraftCategory.TURBOPROP: TURBOPROP_AIRCRAFT,
}


# ============================================================================
# Airline Information Database
# ============================================================================

@dataclass
class AirlineInfo:
    """Information about an airline."""
    code: str  # IATA code
    name: str
    alliance: Alliance = Alliance.NONE
    country: str = ""
    is_low_cost: bool = False
    frequent_flyer_program: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "alliance": self.alliance.value,
            "country": self.country,
            "is_low_cost": self.is_low_cost,
            "frequent_flyer_program": self.frequent_flyer_program,
        }


# Major airlines database
AIRLINES_DATABASE: Dict[str, AirlineInfo] = {
    # US Major Carriers
    "AA": AirlineInfo("AA", "American Airlines", Alliance.ONEWORLD, "US", False, "AAdvantage"),
    "DL": AirlineInfo("DL", "Delta Air Lines", Alliance.SKYTEAM, "US", False, "SkyMiles"),
    "UA": AirlineInfo("UA", "United Airlines", Alliance.STAR_ALLIANCE, "US", False, "MileagePlus"),
    "AS": AirlineInfo("AS", "Alaska Airlines", Alliance.ONEWORLD, "US", False, "Mileage Plan"),
    "WN": AirlineInfo("WN", "Southwest Airlines", Alliance.NONE, "US", True, "Rapid Rewards"),
    "B6": AirlineInfo("B6", "JetBlue Airways", Alliance.NONE, "US", False, "TrueBlue"),
    "NK": AirlineInfo("NK", "Spirit Airlines", Alliance.NONE, "US", True, "Free Spirit"),
    "F9": AirlineInfo("F9", "Frontier Airlines", Alliance.NONE, "US", True, "FRONTIER Miles"),
    "HA": AirlineInfo("HA", "Hawaiian Airlines", Alliance.NONE, "US", False, "HawaiianMiles"),
    
    # European Carriers
    "BA": AirlineInfo("BA", "British Airways", Alliance.ONEWORLD, "GB", False, "Executive Club"),
    "LH": AirlineInfo("LH", "Lufthansa", Alliance.STAR_ALLIANCE, "DE", False, "Miles & More"),
    "AF": AirlineInfo("AF", "Air France", Alliance.SKYTEAM, "FR", False, "Flying Blue"),
    "KL": AirlineInfo("KL", "KLM", Alliance.SKYTEAM, "NL", False, "Flying Blue"),
    "IB": AirlineInfo("IB", "Iberia", Alliance.ONEWORLD, "ES", False, "Iberia Plus"),
    "AY": AirlineInfo("AY", "Finnair", Alliance.ONEWORLD, "FI", False, "Finnair Plus"),
    "SK": AirlineInfo("SK", "SAS", Alliance.STAR_ALLIANCE, "SE", False, "EuroBonus"),
    "LX": AirlineInfo("LX", "Swiss", Alliance.STAR_ALLIANCE, "CH", False, "Miles & More"),
    "OS": AirlineInfo("OS", "Austrian", Alliance.STAR_ALLIANCE, "AT", False, "Miles & More"),
    "TK": AirlineInfo("TK", "Turkish Airlines", Alliance.STAR_ALLIANCE, "TR", False, "Miles&Smiles"),
    "FR": AirlineInfo("FR", "Ryanair", Alliance.NONE, "IE", True, ""),
    "U2": AirlineInfo("U2", "easyJet", Alliance.NONE, "GB", True, "easyJet Plus"),
    "W6": AirlineInfo("W6", "Wizz Air", Alliance.NONE, "HU", True, ""),
    "VY": AirlineInfo("VY", "Vueling", Alliance.NONE, "ES", True, "Vueling Club"),
    
    # Asian Carriers
    "SQ": AirlineInfo("SQ", "Singapore Airlines", Alliance.STAR_ALLIANCE, "SG", False, "KrisFlyer"),
    "CX": AirlineInfo("CX", "Cathay Pacific", Alliance.ONEWORLD, "HK", False, "Asia Miles"),
    "JL": AirlineInfo("JL", "Japan Airlines", Alliance.ONEWORLD, "JP", False, "JAL Mileage Bank"),
    "NH": AirlineInfo("NH", "ANA", Alliance.STAR_ALLIANCE, "JP", False, "ANA Mileage Club"),
    "KE": AirlineInfo("KE", "Korean Air", Alliance.SKYTEAM, "KR", False, "SKYPASS"),
    "OZ": AirlineInfo("OZ", "Asiana Airlines", Alliance.STAR_ALLIANCE, "KR", False, "Asiana Club"),
    "TG": AirlineInfo("TG", "Thai Airways", Alliance.STAR_ALLIANCE, "TH", False, "Royal Orchid Plus"),
    "MH": AirlineInfo("MH", "Malaysia Airlines", Alliance.ONEWORLD, "MY", False, "Enrich"),
    "CA": AirlineInfo("CA", "Air China", Alliance.STAR_ALLIANCE, "CN", False, "PhoenixMiles"),
    "MU": AirlineInfo("MU", "China Eastern", Alliance.SKYTEAM, "CN", False, "Eastern Miles"),
    "CZ": AirlineInfo("CZ", "China Southern", Alliance.SKYTEAM, "CN", False, "Sky Pearl Club"),
    "BR": AirlineInfo("BR", "EVA Air", Alliance.STAR_ALLIANCE, "TW", False, "Infinity MileageLands"),
    "CI": AirlineInfo("CI", "China Airlines", Alliance.SKYTEAM, "TW", False, "Dynasty Flyer"),
    "AI": AirlineInfo("AI", "Air India", Alliance.STAR_ALLIANCE, "IN", False, "Flying Returns"),
    
    # Middle East Carriers
    "EK": AirlineInfo("EK", "Emirates", Alliance.NONE, "AE", False, "Skywards"),
    "QR": AirlineInfo("QR", "Qatar Airways", Alliance.ONEWORLD, "QA", False, "Privilege Club"),
    "EY": AirlineInfo("EY", "Etihad Airways", Alliance.NONE, "AE", False, "Etihad Guest"),
    "SV": AirlineInfo("SV", "Saudia", Alliance.SKYTEAM, "SA", False, "Alfursan"),
    
    # Oceania Carriers
    "QF": AirlineInfo("QF", "Qantas", Alliance.ONEWORLD, "AU", False, "Frequent Flyer"),
    "NZ": AirlineInfo("NZ", "Air New Zealand", Alliance.STAR_ALLIANCE, "NZ", False, "Airpoints"),
    "VA": AirlineInfo("VA", "Virgin Australia", Alliance.NONE, "AU", False, "Velocity"),
    
    # Americas (other)
    "AC": AirlineInfo("AC", "Air Canada", Alliance.STAR_ALLIANCE, "CA", False, "Aeroplan"),
    "WS": AirlineInfo("WS", "WestJet", Alliance.NONE, "CA", False, "WestJet Rewards"),
    "AM": AirlineInfo("AM", "Aeromexico", Alliance.SKYTEAM, "MX", False, "Club Premier"),
    "AV": AirlineInfo("AV", "Avianca", Alliance.STAR_ALLIANCE, "CO", False, "LifeMiles"),
    "LA": AirlineInfo("LA", "LATAM Airlines", Alliance.NONE, "CL", False, "LATAM Pass"),
    "CM": AirlineInfo("CM", "Copa Airlines", Alliance.STAR_ALLIANCE, "PA", False, "ConnectMiles"),
    
    # African Carriers
    "ET": AirlineInfo("ET", "Ethiopian Airlines", Alliance.STAR_ALLIANCE, "ET", False, "ShebaMiles"),
    "SA": AirlineInfo("SA", "South African Airways", Alliance.STAR_ALLIANCE, "ZA", False, "Voyager"),
    "MS": AirlineInfo("MS", "EgyptAir", Alliance.STAR_ALLIANCE, "EG", False, "EgyptAir Plus"),
}


# ============================================================================
# Filter Configuration
# ============================================================================

@dataclass
class AirlineFilterConfig:
    """Configuration for airline filtering."""
    # Airline inclusion/exclusion
    include_airlines: List[str] = field(default_factory=list)  # IATA codes
    exclude_airlines: List[str] = field(default_factory=list)  # IATA codes
    
    # Alliance filtering
    include_alliances: List[Alliance] = field(default_factory=list)
    exclude_alliances: List[Alliance] = field(default_factory=list)
    
    # Low-cost carrier preferences
    include_low_cost: bool = True
    only_low_cost: bool = False
    
    # Aircraft preferences
    preferred_aircraft_categories: List[AircraftCategory] = field(default_factory=list)
    exclude_aircraft_categories: List[AircraftCategory] = field(default_factory=list)
    exclude_aircraft_models: List[str] = field(default_factory=list)
    
    # Loyalty program preferences
    preferred_airlines: List[str] = field(default_factory=list)  # Boost these in ranking
    loyalty_program: Optional[str] = None  # User's primary loyalty program
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "include_airlines": self.include_airlines,
            "exclude_airlines": self.exclude_airlines,
            "include_alliances": [a.value for a in self.include_alliances],
            "exclude_alliances": [a.value for a in self.exclude_alliances],
            "include_low_cost": self.include_low_cost,
            "only_low_cost": self.only_low_cost,
            "preferred_aircraft_categories": [c.value for c in self.preferred_aircraft_categories],
            "exclude_aircraft_categories": [c.value for c in self.exclude_aircraft_categories],
            "exclude_aircraft_models": self.exclude_aircraft_models,
            "preferred_airlines": self.preferred_airlines,
            "loyalty_program": self.loyalty_program,
        }


# ============================================================================
# Filtering Functions
# ============================================================================

def get_airline_info(code: str) -> Optional[AirlineInfo]:
    """Get airline information by IATA code."""
    return AIRLINES_DATABASE.get(code.upper())


def get_airline_alliance(code: str) -> Alliance:
    """Get the alliance for an airline."""
    code = code.upper()
    for alliance, members in ALLIANCE_MAP.items():
        if code in members:
            return alliance
    return Alliance.NONE


def get_airlines_by_alliance(alliance: Alliance) -> List[AirlineInfo]:
    """Get all airlines in an alliance."""
    codes = ALLIANCE_MAP.get(alliance, set())
    return [AIRLINES_DATABASE[code] for code in codes if code in AIRLINES_DATABASE]


def search_airlines(query: str, limit: int = 10) -> List[AirlineInfo]:
    """Search airlines by name or code."""
    query = query.lower()
    results = []
    
    for code, info in AIRLINES_DATABASE.items():
        if query in code.lower() or query in info.name.lower():
            results.append(info)
            if len(results) >= limit:
                break
    
    return results


def get_aircraft_category(aircraft: str) -> Optional[AircraftCategory]:
    """Determine the category of an aircraft model."""
    aircraft = aircraft.upper()
    for category, models in AIRCRAFT_CATEGORY_MAP.items():
        for model in models:
            if model.upper() in aircraft or aircraft in model.upper():
                return category
    return None


def is_wide_body(aircraft: str) -> bool:
    """Check if an aircraft is wide-body."""
    return get_aircraft_category(aircraft) == AircraftCategory.WIDE_BODY


def filter_flights(
    flights: List[Dict[str, Any]],
    config: AirlineFilterConfig,
) -> List[Dict[str, Any]]:
    """
    Filter a list of flights based on airline preferences.
    
    Args:
        flights: List of flight dictionaries (must have 'name' or 'airline' key)
        config: Airline filter configuration
        
    Returns:
        Filtered list of flights
    """
    filtered = []
    
    for flight in flights:
        # Get airline code from flight
        airline_name = flight.get("name") or flight.get("airline") or ""
        airline_code = _extract_airline_code(airline_name)
        
        # Get airline info
        airline_info = get_airline_info(airline_code) if airline_code else None
        alliance = get_airline_alliance(airline_code) if airline_code else Alliance.NONE
        
        # Check airline inclusion
        if config.include_airlines:
            if airline_code not in [a.upper() for a in config.include_airlines]:
                continue
        
        # Check airline exclusion
        if config.exclude_airlines:
            if airline_code in [a.upper() for a in config.exclude_airlines]:
                continue
        
        # Check alliance inclusion
        if config.include_alliances:
            if alliance not in config.include_alliances:
                continue
        
        # Check alliance exclusion
        if config.exclude_alliances:
            if alliance in config.exclude_alliances:
                continue
        
        # Check low-cost preferences
        if airline_info:
            if not config.include_low_cost and airline_info.is_low_cost:
                continue
            if config.only_low_cost and not airline_info.is_low_cost:
                continue
        
        # Check aircraft preferences
        aircraft = flight.get("aircraft") or flight.get("plane") or ""
        if aircraft:
            aircraft_category = get_aircraft_category(aircraft)
            
            if config.preferred_aircraft_categories:
                if aircraft_category and aircraft_category not in config.preferred_aircraft_categories:
                    continue
            
            if config.exclude_aircraft_categories:
                if aircraft_category and aircraft_category in config.exclude_aircraft_categories:
                    continue
            
            if config.exclude_aircraft_models:
                if any(model.upper() in aircraft.upper() for model in config.exclude_aircraft_models):
                    continue
        
        filtered.append(flight)
    
    return filtered


def rank_flights_by_preference(
    flights: List[Dict[str, Any]],
    config: AirlineFilterConfig,
) -> List[Dict[str, Any]]:
    """
    Rank flights by preference, boosting preferred airlines.
    
    Args:
        flights: List of flight dictionaries
        config: Airline filter configuration
        
    Returns:
        Sorted list of flights with preference scoring
    """
    def score_flight(flight: Dict[str, Any]) -> int:
        score = 0
        airline_name = flight.get("name") or flight.get("airline") or ""
        airline_code = _extract_airline_code(airline_name)
        
        # Boost preferred airlines
        if airline_code and airline_code.upper() in [a.upper() for a in config.preferred_airlines]:
            score += 100
        
        # Boost airlines matching loyalty program
        if config.loyalty_program and airline_code:
            airline_info = get_airline_info(airline_code)
            if airline_info and airline_info.frequent_flyer_program:
                # Same program or partner
                if config.loyalty_program.lower() in airline_info.frequent_flyer_program.lower():
                    score += 50
                # Same alliance (can earn miles)
                alliance = get_airline_alliance(airline_code)
                if alliance != Alliance.NONE:
                    score += 25
        
        # Boost wide-body aircraft (comfort)
        aircraft = flight.get("aircraft") or flight.get("plane") or ""
        if aircraft and is_wide_body(aircraft):
            score += 10
        
        return score
    
    # Sort by score (descending), then keep original order for ties
    scored = [(score_flight(f), i, f) for i, f in enumerate(flights)]
    scored.sort(key=lambda x: (-x[0], x[1]))
    
    return [f for _, _, f in scored]


def _extract_airline_code(airline_name: str) -> str:
    """Extract airline IATA code from airline name."""
    if not airline_name:
        return ""
    
    # Check if it's already a code
    if len(airline_name) == 2 and airline_name.isupper():
        return airline_name
    
    # Search by name
    airline_name_lower = airline_name.lower()
    for code, info in AIRLINES_DATABASE.items():
        if info.name.lower() in airline_name_lower or airline_name_lower in info.name.lower():
            return code
    
    # Try common patterns
    name_to_code = {
        "delta": "DL",
        "united": "UA",
        "american": "AA",
        "southwest": "WN",
        "jetblue": "B6",
        "alaska": "AS",
        "spirit": "NK",
        "frontier": "F9",
        "lufthansa": "LH",
        "british airways": "BA",
        "air france": "AF",
        "emirates": "EK",
        "qatar": "QR",
        "singapore": "SQ",
    }
    
    for name, code in name_to_code.items():
        if name in airline_name_lower:
            return code
    
    return ""


# ============================================================================
# Result Classes
# ============================================================================

@dataclass
class FilteredFlightResult:
    """Result of filtered flight search."""
    original_count: int
    filtered_count: int
    filters_applied: List[str]
    flights: List[Dict[str, Any]] = field(default_factory=list)
    preferred_count: int = 0
    alliance_breakdown: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_count": self.original_count,
            "filtered_count": self.filtered_count,
            "filters_applied": self.filters_applied,
            "flights": self.flights,
            "preferred_count": self.preferred_count,
            "alliance_breakdown": self.alliance_breakdown,
        }


def apply_airline_filters(
    flights: List[Dict[str, Any]],
    include_airlines: Optional[List[str]] = None,
    exclude_airlines: Optional[List[str]] = None,
    alliances: Optional[List[str]] = None,
    exclude_alliances: Optional[List[str]] = None,
    include_low_cost: bool = True,
    only_low_cost: bool = False,
    wide_body_only: bool = False,
    exclude_regional: bool = False,
    preferred_airlines: Optional[List[str]] = None,
    loyalty_program: Optional[str] = None,
) -> FilteredFlightResult:
    """
    Apply airline filters to flight results.
    
    Args:
        flights: List of flight dictionaries
        include_airlines: Only include these airlines (IATA codes)
        exclude_airlines: Exclude these airlines (IATA codes)
        alliances: Only include these alliances
        exclude_alliances: Exclude these alliances
        include_low_cost: Include low-cost carriers
        only_low_cost: Only show low-cost carriers
        wide_body_only: Only show wide-body aircraft
        exclude_regional: Exclude regional jets/turboprops
        preferred_airlines: Airlines to prioritize in ranking
        loyalty_program: User's loyalty program for ranking
        
    Returns:
        FilteredFlightResult with filtered and ranked flights
    """
    # Build config
    config = AirlineFilterConfig(
        include_airlines=include_airlines or [],
        exclude_airlines=exclude_airlines or [],
        include_alliances=[Alliance(a) for a in (alliances or []) if a in [e.value for e in Alliance]],
        exclude_alliances=[Alliance(a) for a in (exclude_alliances or []) if a in [e.value for e in Alliance]],
        include_low_cost=include_low_cost,
        only_low_cost=only_low_cost,
        preferred_aircraft_categories=[AircraftCategory.WIDE_BODY] if wide_body_only else [],
        exclude_aircraft_categories=[AircraftCategory.REGIONAL, AircraftCategory.TURBOPROP] if exclude_regional else [],
        preferred_airlines=preferred_airlines or [],
        loyalty_program=loyalty_program,
    )
    
    # Track filters applied
    filters_applied = []
    if include_airlines:
        filters_applied.append(f"Include: {', '.join(include_airlines)}")
    if exclude_airlines:
        filters_applied.append(f"Exclude: {', '.join(exclude_airlines)}")
    if alliances:
        filters_applied.append(f"Alliances: {', '.join(alliances)}")
    if exclude_alliances:
        filters_applied.append(f"Exclude alliances: {', '.join(exclude_alliances)}")
    if not include_low_cost:
        filters_applied.append("No low-cost carriers")
    if only_low_cost:
        filters_applied.append("Low-cost only")
    if wide_body_only:
        filters_applied.append("Wide-body only")
    if exclude_regional:
        filters_applied.append("No regional aircraft")
    
    # Apply filters
    filtered = filter_flights(flights, config)
    
    # Rank by preference
    if preferred_airlines or loyalty_program:
        filtered = rank_flights_by_preference(filtered, config)
        if preferred_airlines:
            filters_applied.append(f"Preferred: {', '.join(preferred_airlines)}")
        if loyalty_program:
            filters_applied.append(f"Loyalty: {loyalty_program}")
    
    # Count preferred airlines in results
    preferred_count = 0
    if preferred_airlines:
        for flight in filtered:
            airline_name = flight.get("name") or flight.get("airline") or ""
            airline_code = _extract_airline_code(airline_name)
            if airline_code and airline_code.upper() in [a.upper() for a in preferred_airlines]:
                preferred_count += 1
    
    # Alliance breakdown
    alliance_breakdown: Dict[str, int] = {}
    for flight in filtered:
        airline_name = flight.get("name") or flight.get("airline") or ""
        airline_code = _extract_airline_code(airline_name)
        alliance = get_airline_alliance(airline_code) if airline_code else Alliance.NONE
        alliance_name = alliance.value
        alliance_breakdown[alliance_name] = alliance_breakdown.get(alliance_name, 0) + 1
    
    return FilteredFlightResult(
        original_count=len(flights),
        filtered_count=len(filtered),
        filters_applied=filters_applied,
        flights=filtered,
        preferred_count=preferred_count,
        alliance_breakdown=alliance_breakdown,
    )


# ============================================================================
# Convenience Functions
# ============================================================================

def get_low_cost_carriers() -> List[AirlineInfo]:
    """Get list of low-cost carriers."""
    return [info for info in AIRLINES_DATABASE.values() if info.is_low_cost]


def get_airlines_with_program(program_name: str) -> List[AirlineInfo]:
    """Get airlines with a specific frequent flyer program."""
    program_lower = program_name.lower()
    results = []
    
    for info in AIRLINES_DATABASE.values():
        if program_lower in info.frequent_flyer_program.lower():
            results.append(info)
    
    # Also add alliance partners
    if results:
        alliance = results[0].alliance
        if alliance != Alliance.NONE:
            for code in ALLIANCE_MAP.get(alliance, set()):
                if code in AIRLINES_DATABASE and AIRLINES_DATABASE[code] not in results:
                    results.append(AIRLINES_DATABASE[code])
    
    return results
