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
        return [
            SEARCH_FLIGHTS_TOOL,
            SEARCH_AIRPORT_TOOL,
            COMPARE_DATES_TOOL,
        ]
    
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
