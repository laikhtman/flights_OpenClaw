"""
MCP (Model Context Protocol) Server for fast-flights.

This module provides an MCP server that exposes flight search functionality
as tools that can be used by AI agents like Claude Desktop, OpenClaw, etc.

Run with:
    python -m fast_flights.mcp_server

Or configure in Claude Desktop / MCP client:
    {
        "mcpServers": {
            "fast-flights": {
                "command": "python",
                "args": ["-m", "fast_flights.mcp_server"]
            }
        }
    }

Available Tools:
    - search_flights: Search for flights between airports
    - search_airport: Find airport codes by name or city
    - compare_flight_dates: Compare prices across multiple dates
    - track_price: Start tracking a route for price changes
    - get_price_history: Get historical prices for a route
    - set_price_alert: Set an alert when price drops below target
    - get_tracked_routes: List all tracked routes
    - get_price_alerts: List all price alerts
"""

from __future__ import annotations

import json
import re
import logging
from typing import Any, Sequence

# Check for MCP availability
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# Import our agent API
from .agent_api import search_flights, search_airports, compare_flight_dates
from .schema_v2 import FlightSearchRequest, PYDANTIC_AVAILABLE

# Import price tracking
try:
    from .price_tracker import get_price_tracker, PriceTracker
    from .price_storage import get_price_storage
    PRICE_TRACKING_AVAILABLE = True
except ImportError:
    PRICE_TRACKING_AVAILABLE = False

# Import flexible dates
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

logger = logging.getLogger(__name__)

# Tool definitions
SEARCH_FLIGHTS_TOOL = Tool(
    name="search_flights",
    description="""Search for flights between airports on Google Flights.

Use this tool to find available flights, prices, and schedules.
Returns flight options with prices, times, stops, and duration.

The 'current_price' field indicates if prices are currently:
- "low": Good time to book
- "typical": Normal pricing
- "high": Prices above average

Example: Search for flights from New York (JFK) to Los Angeles (LAX)
on 2025-06-15 for 2 adults in economy class.""",
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
                "description": "Destination airport IATA code (e.g., 'SFO', 'LHR', 'NRT')",
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
                "minimum": 0,
                "maximum": 8
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "description": "Seat class",
                "default": "economy"
            },
            "max_stops": {
                "type": "integer",
                "description": "Maximum number of stops (0=nonstop, 1, 2). Omit for any.",
                "minimum": 0,
                "maximum": 2
            }
        },
        "required": ["origin", "destination", "departure_date"]
    }
)

SEARCH_AIRPORT_TOOL = Tool(
    name="search_airport",
    description="""Search for airport codes by name or city.

Use this tool when you know the city/airport name but not the IATA code.
Returns a list of matching airports with their codes.

Example: Search for airports in "Tokyo" to find NRT (Narita) or HND (Haneda).""",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Airport or city name to search for (e.g., 'Tokyo', 'Los Angeles', 'Heathrow')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10,
                "minimum": 1,
                "maximum": 50
            }
        },
        "required": ["query"]
    }
)

COMPARE_DATES_TOOL = Tool(
    name="compare_flight_dates",
    description="""Compare flight prices across multiple dates.

Use this tool to help users find the cheapest days to fly.
Returns price comparisons for each date with a recommendation.

Example: Compare prices for JFK to LAX on 2025-06-15, 2025-06-16, and 2025-06-17.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "destination": {
                "type": "string",
                "description": "Destination airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "dates": {
                "type": "array",
                "items": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                "description": "List of dates to compare (YYYY-MM-DD format)",
                "minItems": 2,
                "maxItems": 7
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            }
        },
        "required": ["origin", "destination", "dates"]
    }
)

# Price Tracking Tools
TRACK_PRICE_TOOL = Tool(
    name="track_price",
    description="""Start tracking a flight route for price changes.

Use this tool to monitor prices over time. The tracker will periodically
check prices and record them to a history database.

Example: Track JFK to LAX on 2025-06-15, checking every 30 minutes.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
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
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "check_interval_minutes": {
                "type": "integer",
                "description": "How often to check prices (in minutes)",
                "default": 60,
                "minimum": 15,
                "maximum": 1440
            }
        },
        "required": ["origin", "destination", "departure_date"]
    }
)

GET_PRICE_HISTORY_TOOL = Tool(
    name="get_price_history",
    description="""Get historical prices for a flight route.

Use this tool to see how prices have changed over time.
Returns price records with timestamps and statistics.

Example: Get price history for JFK to LAX over the last 7 days.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
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
                "description": "Specific departure date (YYYY-MM-DD). Omit for all dates.",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "days": {
                "type": "integer",
                "description": "Number of days of history to retrieve",
                "default": 7,
                "minimum": 1,
                "maximum": 90
            }
        },
        "required": ["origin", "destination"]
    }
)

SET_PRICE_ALERT_TOOL = Tool(
    name="set_price_alert",
    description="""Set a price alert for a flight route.

Use this tool to get notified when prices drop below a target.
Supports Discord, Slack webhooks, and email notifications.

Example: Alert me when JFK to LAX on 2025-06-15 drops below $250.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
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
            "target_price": {
                "type": "number",
                "description": "Alert when price drops to or below this amount (in USD)",
                "minimum": 1
            },
            "return_date": {
                "type": "string",
                "description": "Return date for round-trip (YYYY-MM-DD). Omit for one-way.",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "webhook_url": {
                "type": "string",
                "description": "Discord or Slack webhook URL for notifications"
            },
            "email": {
                "type": "string",
                "description": "Email address for notifications (requires SMTP config)"
            }
        },
        "required": ["origin", "destination", "departure_date", "target_price"]
    }
)

GET_TRACKED_ROUTES_TOOL = Tool(
    name="get_tracked_routes",
    description="""List all routes being tracked for price changes.

Use this tool to see what routes are currently being monitored.""",
    inputSchema={
        "type": "object",
        "properties": {
            "active_only": {
                "type": "boolean",
                "description": "Only show active routes",
                "default": True
            }
        },
        "required": []
    }
)

GET_PRICE_ALERTS_TOOL = Tool(
    name="get_price_alerts",
    description="""List all price alerts.

Use this tool to see what price alerts are configured.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Filter by origin airport (optional)"
            },
            "destination": {
                "type": "string",
                "description": "Filter by destination airport (optional)"
            },
            "active_only": {
                "type": "boolean",
                "description": "Only show active (untriggered) alerts",
                "default": True
            }
        },
        "required": []
    }
)

# Flexible Date Search Tools
SEARCH_FLEXIBLE_DATES_TOOL = Tool(
    name="search_flexible_dates",
    description="""Search for flights with flexible departure dates.

Use this tool to find the cheapest days to fly within a date range.
Searches +/- N days around your preferred date and returns price comparisons.

Example: Find the cheapest day to fly JFK to LAX within 3 days of 2025-06-15.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
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
                "description": "Center date for the search (YYYY-MM-DD)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "days_before": {
                "type": "integer",
                "description": "Days before the center date to search",
                "default": 3,
                "minimum": 0,
                "maximum": 7
            },
            "days_after": {
                "type": "integer",
                "description": "Days after the center date to search",
                "default": 3,
                "minimum": 0,
                "maximum": 7
            },
            "return_date": {
                "type": "string",
                "description": "Return date for round-trip (YYYY-MM-DD)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            }
        },
        "required": ["origin", "destination", "departure_date"]
    }
)

SEARCH_WEEKEND_FLIGHTS_TOOL = Tool(
    name="search_weekend_flights",
    description="""Search for flights on weekends only.

Use this tool to find weekend flight prices for the next few weeks.
Returns Saturday and Sunday flight options with prices.

Example: Find weekend flights from NYC to LA for the next 4 weekends.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "destination": {
                "type": "string",
                "description": "Destination airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "start_date": {
                "type": "string",
                "description": "Start searching from this date (YYYY-MM-DD)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "num_weekends": {
                "type": "integer",
                "description": "Number of weekends to search",
                "default": 4,
                "minimum": 1,
                "maximum": 8
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            }
        },
        "required": ["origin", "destination", "start_date"]
    }
)

SEARCH_WEEKDAY_FLIGHTS_TOOL = Tool(
    name="search_weekday_flights",
    description="""Search for flights on specific weekdays.

Use this tool when the user prefers certain days (e.g., Tuesdays/Wednesdays).
Often mid-week flights are cheaper than weekend flights.

Example: Find Tuesday flights from JFK to LAX for the next 4 weeks.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "destination": {
                "type": "string",
                "description": "Destination airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "start_date": {
                "type": "string",
                "description": "Start searching from this date (YYYY-MM-DD)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "weekdays": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                },
                "description": "Days of the week to search",
                "minItems": 1,
                "maxItems": 7
            },
            "num_weeks": {
                "type": "integer",
                "description": "Number of weeks to search",
                "default": 4,
                "minimum": 1,
                "maximum": 8
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            }
        },
        "required": ["origin", "destination", "start_date", "weekdays"]
    }
)

GET_CALENDAR_HEATMAP_TOOL = Tool(
    name="get_calendar_heatmap",
    description="""Get a monthly calendar of flight prices.

Use this tool to see price trends across an entire month.
Returns prices for each day with the cheapest day highlighted.

Example: Show me flight prices for JFK to LAX in June 2025.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "destination": {
                "type": "string",
                "description": "Destination airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "year": {
                "type": "integer",
                "description": "Year (e.g., 2025)",
                "minimum": 2024,
                "maximum": 2026
            },
            "month": {
                "type": "integer",
                "description": "Month (1-12)",
                "minimum": 1,
                "maximum": 12
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            },
            "sample_days": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1, "maximum": 31},
                "description": "Sample specific days only (for faster results). Omit to check all days."
            }
        },
        "required": ["origin", "destination", "year", "month"]
    }
)

SUGGEST_BEST_DATES_TOOL = Tool(
    name="suggest_best_dates",
    description="""Get smart suggestions for the best dates to fly.

Use this tool to find optimal travel dates based on preferences.
Considers price, weekends vs weekdays, and flexibility.

Example: Find the best dates to fly around June 15th with 5 days flexibility.""",
    inputSchema={
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "destination": {
                "type": "string",
                "description": "Destination airport IATA code",
                "minLength": 3,
                "maxLength": 4
            },
            "preferred_date": {
                "type": "string",
                "description": "Preferred departure date (YYYY-MM-DD)",
                "pattern": r"^\d{4}-\d{2}-\d{2}$"
            },
            "flexibility_days": {
                "type": "integer",
                "description": "How flexible (+/- days from preferred)",
                "default": 7,
                "minimum": 1,
                "maximum": 14
            },
            "prefer_weekends": {
                "type": "boolean",
                "description": "Only suggest weekend dates",
                "default": False
            },
            "avoid_weekends": {
                "type": "boolean",
                "description": "Exclude weekend dates from suggestions",
                "default": False
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum suggestions to return",
                "default": 5,
                "minimum": 1,
                "maximum": 10
            },
            "seat_class": {
                "type": "string",
                "enum": ["economy", "premium-economy", "business", "first"],
                "default": "economy"
            },
            "adults": {
                "type": "integer",
                "description": "Number of adult passengers",
                "default": 1,
                "minimum": 1,
                "maximum": 9
            }
        },
        "required": ["origin", "destination", "preferred_date"]
    }
)


def create_mcp_server() -> "Server":
    """
    Create and configure the MCP server with flight search tools.
    
    Returns:
        Configured MCP Server instance
        
    Raises:
        ImportError: If MCP package is not installed
    """
    if not MCP_AVAILABLE:
        raise ImportError(
            "MCP package not installed. Install with: pip install fast-flights[mcp]"
        )
    
    if not PYDANTIC_AVAILABLE:
        raise ImportError(
            "Pydantic package not installed. Install with: pip install fast-flights[mcp]"
        )
    
    server = Server("fast-flights")
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available flight search tools."""
        tools = [
            SEARCH_FLIGHTS_TOOL,
            SEARCH_AIRPORT_TOOL,
            COMPARE_DATES_TOOL,
        ]
        
        # Add price tracking tools if available
        if PRICE_TRACKING_AVAILABLE:
            tools.extend([
                TRACK_PRICE_TOOL,
                GET_PRICE_HISTORY_TOOL,
                SET_PRICE_ALERT_TOOL,
                GET_TRACKED_ROUTES_TOOL,
                GET_PRICE_ALERTS_TOOL,
            ])
        
        # Add flexible date tools if available
        if FLEX_DATES_AVAILABLE:
            tools.extend([
                SEARCH_FLEXIBLE_DATES_TOOL,
                SEARCH_WEEKEND_FLIGHTS_TOOL,
                SEARCH_WEEKDAY_FLIGHTS_TOOL,
                GET_CALENDAR_HEATMAP_TOOL,
                SUGGEST_BEST_DATES_TOOL,
            ])
        
        return tools
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
        """Handle tool calls from the MCP client."""
        logger.info(f"Tool called: {name} with args: {arguments}")
        
        try:
            if name == "search_flights":
                return await _handle_search_flights(arguments)
            elif name == "search_airport":
                return await _handle_search_airport(arguments)
            elif name == "compare_flight_dates":
                return await _handle_compare_dates(arguments)
            elif name == "track_price":
                return await _handle_track_price(arguments)
            elif name == "get_price_history":
                return await _handle_get_price_history(arguments)
            elif name == "set_price_alert":
                return await _handle_set_price_alert(arguments)
            elif name == "get_tracked_routes":
                return await _handle_get_tracked_routes(arguments)
            elif name == "get_price_alerts":
                return await _handle_get_price_alerts(arguments)
            elif name == "search_flexible_dates":
                return await _handle_search_flexible_dates(arguments)
            elif name == "search_weekend_flights":
                return await _handle_search_weekend_flights(arguments)
            elif name == "search_weekday_flights":
                return await _handle_search_weekday_flights(arguments)
            elif name == "get_calendar_heatmap":
                return await _handle_get_calendar_heatmap(arguments)
            elif name == "suggest_best_dates":
                return await _handle_suggest_best_dates(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2)
                )]
        except Exception as e:
            logger.error(f"Error in tool {name}: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "tool": name,
                    "suggestion": "Check input parameters and try again"
                }, indent=2)
            )]
    
    return server


async def _handle_search_flights(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the search_flights tool call."""
    result = search_flights(arguments)
    response = result.to_agent_response()
    
    # Add a human-readable summary at the top
    response["summary"] = result.summary()
    
    return [TextContent(
        type="text",
        text=json.dumps(response, indent=2)
    )]


async def _handle_search_airport(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the search_airport tool call."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    
    airports = search_airports(query, limit=limit)
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "query": query,
            "results": airports,
            "total": len(airports),
            "hint": "Use the 'code' field as origin/destination in search_flights"
        }, indent=2)
    )]


async def _handle_compare_dates(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the compare_flight_dates tool call."""
    result = compare_flight_dates(
        origin=arguments["origin"],
        destination=arguments["destination"],
        dates=arguments["dates"],
        adults=arguments.get("adults", 1),
        seat_class=arguments.get("seat_class", "economy")
    )
    
    return [TextContent(
        type="text",
        text=json.dumps(result, indent=2)
    )]


# Price Tracking Handlers

async def _handle_track_price(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the track_price tool call."""
    if not PRICE_TRACKING_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Price tracking not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    tracker = get_price_tracker()
    route_id = tracker.track_route(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments["departure_date"],
        return_date=arguments.get("return_date"),
        seat_class=arguments.get("seat_class", "economy"),
        check_interval_minutes=arguments.get("check_interval_minutes", 60),
    )
    
    # Do an immediate price check
    record = tracker.check_price(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments["departure_date"],
        return_date=arguments.get("return_date"),
        seat_class=arguments.get("seat_class", "economy"),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "status": "success",
            "message": f"Now tracking {arguments['origin']} → {arguments['destination']}",
            "route_id": route_id,
            "departure_date": arguments["departure_date"],
            "check_interval_minutes": arguments.get("check_interval_minutes", 60),
            "current_price": record.price if record else None,
            "price_level": record.price_level if record else None,
        }, indent=2)
    )]


async def _handle_get_price_history(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the get_price_history tool call."""
    if not PRICE_TRACKING_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Price tracking not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    tracker = get_price_tracker()
    
    # Get history
    history = tracker.get_price_history(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments.get("departure_date"),
        days=arguments.get("days", 7),
    )
    
    # Get stats
    stats = tracker.get_price_stats(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments.get("departure_date"),
        days=arguments.get("days", 7),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{arguments['origin']} → {arguments['destination']}",
            "departure_date": arguments.get("departure_date", "all dates"),
            "days_analyzed": arguments.get("days", 7),
            "statistics": stats,
            "price_history": [
                {
                    "price": r.price,
                    "price_level": r.price_level,
                    "airline": r.airline,
                    "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                }
                for r in history[:20]  # Limit to 20 most recent
            ],
            "total_records": len(history),
        }, indent=2)
    )]


async def _handle_set_price_alert(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the set_price_alert tool call."""
    if not PRICE_TRACKING_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Price tracking not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    tracker = get_price_tracker()
    alert_id = tracker.set_alert(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments["departure_date"],
        target_price=arguments["target_price"],
        return_date=arguments.get("return_date"),
        webhook_url=arguments.get("webhook_url"),
        email=arguments.get("email"),
    )
    
    # Check current price for comparison
    record = tracker.check_price(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments["departure_date"],
        return_date=arguments.get("return_date"),
    )
    
    current_price = record.price if record else None
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "status": "success",
            "message": f"Alert set for {arguments['origin']} → {arguments['destination']}",
            "alert_id": alert_id,
            "target_price": arguments["target_price"],
            "current_price": current_price,
            "will_trigger": current_price <= arguments["target_price"] if current_price else None,
            "notification_method": "webhook" if arguments.get("webhook_url") else ("email" if arguments.get("email") else "callback"),
        }, indent=2)
    )]


async def _handle_get_tracked_routes(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the get_tracked_routes tool call."""
    if not PRICE_TRACKING_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Price tracking not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    tracker = get_price_tracker()
    routes = tracker.get_tracked_routes(
        active_only=arguments.get("active_only", True)
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "total_routes": len(routes),
            "routes": [
                {
                    "id": r.id,
                    "route": f"{r.origin} → {r.destination}",
                    "departure_date": r.departure_date,
                    "return_date": r.return_date,
                    "seat_class": r.seat_class,
                    "check_interval_minutes": r.check_interval_minutes,
                    "is_active": r.is_active,
                    "last_price": r.last_price,
                    "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                }
                for r in routes
            ],
        }, indent=2)
    )]


async def _handle_get_price_alerts(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the get_price_alerts tool call."""
    if not PRICE_TRACKING_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Price tracking not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    tracker = get_price_tracker()
    alerts = tracker.get_alerts(
        origin=arguments.get("origin"),
        destination=arguments.get("destination"),
        active_only=arguments.get("active_only", True),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "total_alerts": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "route": f"{a.origin} → {a.destination}",
                    "departure_date": a.departure_date,
                    "target_price": a.target_price,
                    "is_active": a.is_active,
                    "has_webhook": bool(a.webhook_url),
                    "has_email": bool(a.email),
                    "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
                }
                for a in alerts
            ],
        }, indent=2)
    )]


# Flexible Date Search Handlers

async def _handle_search_flexible_dates(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the search_flexible_dates tool call."""
    if not FLEX_DATES_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Flexible dates module not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    result = search_flexible_dates(
        origin=arguments["origin"],
        destination=arguments["destination"],
        departure_date=arguments["departure_date"],
        days_before=arguments.get("days_before", 3),
        days_after=arguments.get("days_after", 3),
        return_date=arguments.get("return_date"),
        seat_class=arguments.get("seat_class", "economy"),
        adults=arguments.get("adults", 1),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{result.origin} → {result.destination}",
            "base_date": result.base_date,
            "dates_searched": result.dates_searched,
            "recommendation": result.recommendation,
            "cheapest_date": result.cheapest_date.to_dict() if result.cheapest_date else None,
            "most_expensive_date": result.most_expensive_date.to_dict() if result.most_expensive_date else None,
            "average_price": result.average_price,
            "all_dates": [r.to_dict() for r in result.results],
        }, indent=2)
    )]


async def _handle_search_weekend_flights(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the search_weekend_flights tool call."""
    if not FLEX_DATES_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Flexible dates module not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    result = search_weekend_flights(
        origin=arguments["origin"],
        destination=arguments["destination"],
        start_date=arguments["start_date"],
        num_weekends=arguments.get("num_weekends", 4),
        seat_class=arguments.get("seat_class", "economy"),
        adults=arguments.get("adults", 1),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{result.origin} → {result.destination}",
            "weekends_searched": result.dates_searched // 2,  # Approx weekends
            "recommendation": result.recommendation,
            "cheapest_weekend": result.cheapest_date.to_dict() if result.cheapest_date else None,
            "average_price": result.average_price,
            "weekend_dates": [r.to_dict() for r in result.results],
        }, indent=2)
    )]


async def _handle_search_weekday_flights(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the search_weekday_flights tool call."""
    if not FLEX_DATES_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Flexible dates module not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    result = search_weekday_flights(
        origin=arguments["origin"],
        destination=arguments["destination"],
        start_date=arguments["start_date"],
        weekdays=arguments["weekdays"],
        num_weeks=arguments.get("num_weeks", 4),
        seat_class=arguments.get("seat_class", "economy"),
        adults=arguments.get("adults", 1),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{result.origin} → {result.destination}",
            "weekdays_searched": arguments["weekdays"],
            "weeks_covered": arguments.get("num_weeks", 4),
            "recommendation": result.recommendation,
            "cheapest_day": result.cheapest_date.to_dict() if result.cheapest_date else None,
            "average_price": result.average_price,
            "dates": [r.to_dict() for r in result.results],
        }, indent=2)
    )]


async def _handle_get_calendar_heatmap(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the get_calendar_heatmap tool call."""
    if not FLEX_DATES_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Flexible dates module not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    heatmap = get_calendar_heatmap(
        origin=arguments["origin"],
        destination=arguments["destination"],
        year=arguments["year"],
        month=arguments["month"],
        seat_class=arguments.get("seat_class", "economy"),
        adults=arguments.get("adults", 1),
        sample_days=arguments.get("sample_days"),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{heatmap.origin} → {heatmap.destination}",
            "month": f"{heatmap.month_name} {heatmap.year}",
            "cheapest_day": heatmap.cheapest_day.to_dict() if heatmap.cheapest_day else None,
            "cheapest_week": heatmap.cheapest_week,
            "price_range": heatmap.price_range,
            "days": [d.to_dict() for d in heatmap.days],
        }, indent=2)
    )]


async def _handle_suggest_best_dates(arguments: dict[str, Any]) -> Sequence[TextContent]:
    """Handle the suggest_best_dates tool call."""
    if not FLEX_DATES_AVAILABLE:
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": "Flexible dates module not available",
                "suggestion": "Install with: pip install fast-flights[agent]"
            }, indent=2)
        )]
    
    result = suggest_best_dates(
        origin=arguments["origin"],
        destination=arguments["destination"],
        preferred_date=arguments["preferred_date"],
        flexibility_days=arguments.get("flexibility_days", 7),
        prefer_weekends=arguments.get("prefer_weekends", False),
        avoid_weekends=arguments.get("avoid_weekends", False),
        max_results=arguments.get("max_results", 5),
        seat_class=arguments.get("seat_class", "economy"),
        adults=arguments.get("adults", 1),
    )
    
    return [TextContent(
        type="text",
        text=json.dumps({
            "route": f"{result.origin} → {result.destination}",
            "preferred_date": arguments["preferred_date"],
            "flexibility": f"+/- {arguments.get('flexibility_days', 7)} days",
            "recommendation": result.recommendation,
            "suggestions": [
                {
                    "rank": i + 1,
                    "date": r.date,
                    "day_of_week": r.day_of_week,
                    "price": r.price,
                    "is_weekend": r.is_weekend,
                    "airline": r.airline,
                }
                for i, r in enumerate(result.results)
            ],
            "average_price": result.average_price,
        }, indent=2)
    )]


async def main():
    """Run the MCP server."""
    if not MCP_AVAILABLE:
        print("Error: MCP package not installed.")
        print("Install with: pip install fast-flights[mcp]")
        return
    
    if not PYDANTIC_AVAILABLE:
        print("Error: Pydantic package not installed.")
        print("Install with: pip install fast-flights[mcp]")
        return
    
    logger.info("Starting fast-flights MCP server...")
    server = create_mcp_server()
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


def run():
    """Entry point for the MCP server script."""
    import asyncio
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    asyncio.run(main())


if __name__ == "__main__":
    run()
