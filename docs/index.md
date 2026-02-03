# ✈️ flights_OpenClaw

**AI-Agent-Ready Google Flights Scraper for Python**

*Built for [OpenClaw](https://openclaw.io) and AI Agents*

[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)
[![OpenClaw Ready](https://img.shields.io/badge/OpenClaw-Ready-orange.svg)](https://openclaw.io)

---

## 🤖 Overview

**flights_OpenClaw** is a fork of [fast-flights](https://github.com/AWeirdDev/flights) enhanced for AI agent integration. It scrapes Google Flights using Base64-encoded Protobuf queries and returns structured, validated responses perfect for LLM applications.

### Why this fork?

| Feature | Original | 🦎 This Fork |
|---------|----------|-----------|
| JSON Output | Manual | Built-in `model_dump()` |
| Error Handling | Exceptions | Structured responses |
| Schema Validation | None | Pydantic models |
| MCP Support | None | ✅ Full MCP server |
| OpenClaw Ready | None | ✅ Native support |
| Agent API | None | `search_flights()` |
| Async Support | None | ✅ `search_flights_async()` |
| Reliability | Basic | Retry, rate limiting |

---

## Installation

```bash
# Core only
pip install fast-flights

# With AI agent support
pip install fast-flights[agent]

# With MCP server
pip install fast-flights[mcp]

# Everything
pip install fast-flights[all]
```

---

## Quick Start

### Standard API

```python
from fast_flights import get_flights, FlightData, Passengers

result = get_flights(
    flight_data=[
        FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")
    ],
    trip="one-way",
    seat="economy",
    passengers=Passengers(adults=2),
    fetch_mode="fallback",
)

print(f"Price level: {result.current_price}")
for flight in result.flights:
    print(f"{flight.name}: {flight.price}")
```

### Agent API

```python
from fast_flights import search_flights

result = search_flights({
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2025-06-15",
    "adults": 2
})

# Never throws - check success
if result.success:
    print(result.summary())
else:
    print(f"Error: {result.error}")
```

---

## Documentation

<div class="grid cards" markdown>

-   :material-robot:{ .lg .middle } **AI Agent Integration**

    ---

    Complete guide for integrating with AI agents like OpenClaw and Claude.

    [:octicons-arrow-right-24: Agent Guide](AI_AGENT_INTEGRATION.md)

-   :material-server:{ .lg .middle } **MCP Server**

    ---

    Run as an MCP server for Claude Desktop and other AI assistants.

    [:octicons-arrow-right-24: MCP Setup](mcp.md)

-   :material-filter:{ .lg .middle } **Filters & Options**

    ---

    All available search parameters and how to use them.

    [:octicons-arrow-right-24: Filters](filters.md)

-   :material-backup-restore:{ .lg .middle } **Fallback Modes**

    ---

    Understanding fetch modes for reliability.

    [:octicons-arrow-right-24: Fallbacks](fallbacks.md)

-   :material-airplane:{ .lg .middle } **Airport Codes**

    ---

    Search and discover IATA airport codes.

    [:octicons-arrow-right-24: Airports](airports.md)

-   :material-desktop-classic:{ .lg .middle } **Local Playwright**

    ---

    Set up local Playwright for maximum control.

    [:octicons-arrow-right-24: Local Setup](local.md)

</div>

---

## Roadmap

### ✅ Phase 1: Core API (Complete)
- Pydantic models for validation
- Unified `search_flights()` API
- Structured error handling
- Comprehensive docstrings

### ✅ Phase 2: MCP Server (Complete)
- MCP server implementation
- Tool definitions for search, airports, date comparison
- Configuration for Claude Desktop & OpenClaw

### ✅ Phase 3: Reliability (Complete)
- Retry logic with exponential backoff
- Thread-safe rate limiting
- Centralized configuration management

### ✅ Phase 4: Async Support (Complete)
- Async wrapper functions
- Concurrent multi-route searches
- Date range search

---

## Credits

Forked from [**fast-flights**](https://github.com/AWeirdDev/flights) by [@AWeirdDev](https://github.com/AWeirdDev).

The original project brilliantly reverse-engineered Google Flights' Protobuf query system. All credit for the core scraping logic goes to the original author!

---

<div align="center">

Made with ☕ by [laikhtman](https://github.com/laikhtman) • Original by [AWeirdDev](https://github.com/AWeirdDev)

</div>

