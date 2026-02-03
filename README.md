<div align="center">

# ✈️ flights_OpenClaw

A fast, AI-agent-ready Google Flights scraper for Python.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[**Quick Start**](#quick-start) • [**AI Agent API**](#ai-agent-integration) • [**Docs**](docs/) • [**Roadmap**](#roadmap)

```bash
pip install fast-flights
```

</div>

---

## What is this?

This is a fork of [AWeirdDev/flights](https://github.com/AWeirdDev/flights) — a brilliant Google Flights scraper that uses Base64-encoded Protobuf to query flight data. Huge thanks to [@AWeirdDev](https://github.com/AWeirdDev) for the original work and clever reverse-engineering! 🙏

**This fork adds:**
- 🤖 AI agent-friendly API with structured JSON responses
- 📦 Pydantic models for validation & serialization  
- 🔧 MCP (Model Context Protocol) server support
- 🛡️ Structured error handling with recovery suggestions
- 📚 Comprehensive documentation

---

## Quick Start

### Basic Usage

```python
from fast_flights import get_flights, FlightData, Passengers

result = get_flights(
    flight_data=[
        FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")
    ],
    trip="one-way",
    seat="economy",
    passengers=Passengers(adults=2),
    fetch_mode="fallback",  # Recommended for reliability
)

print(f"Price level: {result.current_price}")  # low, typical, or high
for flight in result.flights:
    print(f"{flight.name}: {flight.price} - {flight.duration}")
```

### Round-trip Example

```python
result = get_flights(
    flight_data=[
        FlightData(date="2025-06-15", from_airport="SFO", to_airport="LHR"),
        FlightData(date="2025-06-22", from_airport="LHR", to_airport="SFO"),
    ],
    trip="round-trip",
    seat="business",
    adults=1,
)
```

---

## AI Agent Integration

Built for seamless integration with AI agents like OpenClaw, Claude, and custom LLM applications.

### Install with Agent Support

```bash
pip install fast-flights[agent]
```

### Simple Agent API

```python
from fast_flights import search_flights

# Dict input - perfect for LLM function calling
result = search_flights({
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2025-06-15",
    "adults": 2,
    "seat_class": "economy"
})

# Structured response for agents
response = result.to_agent_response()
print(response["status"])  # "success" or "error"
print(response["data"]["best_flight"])

# Human-readable summary
print(result.summary())
# "Found 12 flight option(s). Price level: low. Best option: Delta at $249..."
```

### Features for AI Agents

| Feature | Description |
|---------|-------------|
| **Structured Responses** | JSON-serializable Pydantic models |
| **Never Throws** | Errors captured in response, not exceptions |
| **Error Codes** | Machine-readable codes like `RATE_LIMITED`, `NO_FLIGHTS_FOUND` |
| **Recovery Hints** | Suggested actions for each error type |
| **Validation** | Input validation with clear error messages |

### Async API

```python
import asyncio
from fast_flights import search_flights_async, search_multiple_routes

async def main():
    # Single async search
    result = await search_flights_async({
        "origin": "JFK",
        "destination": "LAX",
        "departure_date": "2025-06-15"
    })
    
    # Concurrent multi-route search (3x faster!)
    routes = [
        {"origin": "JFK", "destination": "LAX", "departure_date": "2025-06-15"},
        {"origin": "SFO", "destination": "ORD", "departure_date": "2025-06-15"},
        {"origin": "MIA", "destination": "SEA", "departure_date": "2025-06-15"},
    ]
    results = await search_multiple_routes(routes)

asyncio.run(main())
```

---

## MCP Server (Claude Desktop / OpenClaw)

Use fast-flights as an MCP tool server for AI assistants.

### Quick Setup

```bash
pip install fast-flights[mcp]
```

Add to Claude Desktop config (`claude_desktop_config.json`):

```json
{
    "mcpServers": {
        "fast-flights": {
            "command": "python",
            "args": ["-m", "fast_flights.mcp_server"]
        }
    }
}
```

**Available Tools:**
- `search_flights` - Search flights with prices, times, stops
- `search_airport` - Find airport codes by city name
- `compare_flight_dates` - Compare prices across dates

See [MCP Documentation](docs/mcp.md) for full details.

---

## Fetch Modes

| Mode | Speed | Reliability | Notes |
|------|-------|-------------|-------|
| `common` | ⚡ Fast | Medium | Direct HTTP, may be blocked |
| `fallback` | ⚡ Fast | High | **Recommended** - falls back to Playwright |
| `force-fallback` | 🐢 Slow | High | Always uses Playwright |
| `local` | 🐢 Slow | High | Requires local Playwright install |
| `bright-data` | ⚡ Fast | Very High | Requires API key |

---

## Installation Options

```bash
# Core only
pip install fast-flights

# With AI agent support (Pydantic models)
pip install fast-flights[agent]

# With MCP server support
pip install fast-flights[mcp]

# With local Playwright
pip install fast-flights[local]

# Everything
pip install fast-flights[all]
```

---

## Roadmap

### ✅ Phase 1: Core API Improvements (Complete)
- [x] Pydantic models for schema validation
- [x] Unified `search_flights()` function for agents
- [x] Structured error handling with recovery suggestions
- [x] Comprehensive docstrings and type hints

### ✅ Phase 2: MCP Server (Complete)
- [x] MCP server implementation (`fast_flights.mcp_server`)
- [x] Tool definitions for flight search, airport lookup, date comparison
- [x] Configuration file for Claude Desktop / OpenClaw

### ✅ Phase 3: Reliability (Complete)
- [x] Retry logic with exponential backoff
- [x] Thread-safe rate limiting
- [x] Centralized configuration management

### ✅ Phase 4: Async Support (Complete)
- [x] Async wrapper functions
- [x] Concurrent multi-route searches
- [x] Date range search

### 💡 Future Ideas
- Price tracking & alerts
- Flexible date search (+/- days)
- Airline filtering
- HTTP API wrapper (FastAPI)

---

## Configuration

Configure behavior via environment variables or code:

```python
from fast_flights import configure, get_config

# Configure via code
configure(
    max_retries=3,
    retry_base_delay=1.0,
    rate_limit_requests=10,
    rate_limit_window=60,
    fetch_mode="fallback"
)

# Or via environment variables
# FAST_FLIGHTS_MAX_RETRIES=3
# FAST_FLIGHTS_FETCH_MODE=fallback
# FAST_FLIGHTS_RATE_LIMIT_REQUESTS=10
```

### Retry with Backoff

```python
from fast_flights import retry_with_backoff

@retry_with_backoff(max_retries=3, base_delay=1.0)
def my_search():
    return search_flights({"origin": "JFK", "destination": "LAX", ...})
```

### Rate Limiting

```python
from fast_flights import get_rate_limiter, rate_limited

# Automatic rate limiting
@rate_limited
def search():
    return search_flights(...)

# Or manual control
limiter = get_rate_limiter()
with limiter:
    result = search_flights(...)
```

---

## Documentation

- [AI Agent Integration Guide](docs/AI_AGENT_INTEGRATION.md)
- [MCP Server Setup](docs/mcp.md)
- [Filters & Options](docs/filters.md)
- [Fallback Modes](docs/fallbacks.md)
- [Airport Codes](docs/airports.md)
- [Local Playwright Setup](docs/local.md)

---

## Credits

This project is a fork of [**fast-flights**](https://github.com/AWeirdDev/flights) by [@AWeirdDev](https://github.com/AWeirdDev).

The original library brilliantly reverse-engineered Google Flights' Protobuf-based query system. Check out the [original README](https://github.com/AWeirdDev/flights) for the fascinating story of how it was built!

---

## Contributing

Contributions welcome! Whether it's bug fixes, new features, or documentation improvements — PRs are appreciated.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

<div align="center">

---

Made with ☕ by [laikhtman](https://github.com/laikhtman) • Original by [AWeirdDev](https://github.com/AWeirdDev)

</div>
