<div align="center">

# ✈️ flights_OpenClaw

**AI-Agent-Ready Google Flights Scraper for Python**

*Built for [OpenClaw](https://openclaw.io) and AI Agents*

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)
[![OpenClaw Ready](https://img.shields.io/badge/OpenClaw-Ready-orange.svg)](https://openclaw.io)
[![PyPI](https://img.shields.io/pypi/v/fast-flights.svg)](https://pypi.org/project/fast-flights/)

[**Quick Start**](#quick-start) • [**🤖 AI Agent API**](#ai-agent-integration) • [**🔧 MCP Server**](#mcp-server-claude-desktop--openclaw) • [**📚 Docs**](docs/) • [**🗺️ Roadmap**](#roadmap)

```bash
pip install fast-flights[agent]  # For AI agents
pip install fast-flights[mcp]    # For MCP server
```

</div>

---

## 🤖 What is this?

This is a fork of [AWeirdDev/flights](https://github.com/AWeirdDev/flights) — a brilliant Google Flights scraper that uses Base64-encoded Protobuf to query flight data. Huge thanks to [@AWeirdDev](https://github.com/AWeirdDev) for the original work and clever reverse-engineering! 🙏

**This fork adds:**
- 🤖 **AI Agent API** - Structured JSON responses for LLM function calling
- 🦎 **OpenClaw Ready** - Works seamlessly with OpenClaw AI agents
- 🔧 **MCP Server** - Model Context Protocol for Claude Desktop & AI assistants
- 📦 **Pydantic Models** - Type-safe validation & serialization  
- 🛡️ **Error Handling** - Structured errors with recovery suggestions
- ⚡ **Reliability** - Retry logic, rate limiting, config management
- 📚 **Documentation** - Comprehensive guides for AI integration

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

## 🔧 MCP Server (Claude Desktop / OpenClaw)

Use fast-flights as an MCP tool server for AI assistants like **Claude Desktop** and **OpenClaw**.

### 🦎 OpenClaw Setup

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

### 🤖 Claude Desktop Setup

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

**Available MCP Tools:**
| Tool | Description |
|------|-------------|
| `search_flights` | Search flights with prices, times, stops |
| `search_airport` | Find airport codes by city name |
| `compare_flight_dates` | Compare prices across multiple dates |
| `track_price` | Start tracking a route for price changes |
| `get_price_history` | Get historical prices for a route |
| `set_price_alert` | Set alert when price drops below target |

See [MCP Documentation](docs/mcp.md) for full details.

---

## 📊 Price Tracking

Track prices over time and get notified when they drop.

### Start Tracking

```python
from fast_flights import get_price_tracker

tracker = get_price_tracker()

# Track a route
route_id = tracker.track_route(
    origin="JFK",
    destination="LAX",
    departure_date="2025-06-15",
    check_interval_minutes=30,  # Check every 30 min
)

# Set a price alert with Discord webhook
alert_id = tracker.set_alert(
    origin="JFK",
    destination="LAX",
    departure_date="2025-06-15",
    target_price=250,  # Alert when <= $250
    webhook_url="https://discord.com/api/webhooks/...",
)

# Start background monitoring
tracker.start()
```

### Get Price History

```python
# View price history
history = tracker.get_price_history("JFK", "LAX", departure_date="2025-06-15")
for record in history:
    print(f"{record.recorded_at}: ${record.price} ({record.price_level})")

# Get statistics
stats = tracker.get_price_stats("JFK", "LAX", departure_date="2025-06-15", days=7)
print(f"Min: ${stats['min_price']}, Max: ${stats['max_price']}, Avg: ${stats['avg_price']}")
```

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

### ✅ Phase 5: Price Tracking & Alerts (Complete)
- [x] **Price history storage**
  - [x] SQLite backend for local storage
  - [x] Schema for route + date + price + timestamp
- [x] **Price monitoring**
  - [x] Background scheduler with threading
  - [x] Configurable check intervals
  - [x] Price change detection
- [x] **Alert system**
  - [x] Webhook notifications (Discord, Slack)
  - [x] Email alerts via SMTP
  - [x] Price threshold triggers
- [x] **MCP tools**
  - [x] `track_price` - Start tracking a route
  - [x] `get_price_history` - Retrieve historical prices
  - [x] `set_price_alert` - Configure alert thresholds
  - [x] `get_tracked_routes` - List tracked routes
  - [x] `get_price_alerts` - List price alerts

### 🗓️ Phase 6: Flexible Date Search ✅
- [x] **Date range queries**
  - [x] `+/- N days` parameter for searches
  - [x] Weekend-only search option
  - [x] Specific weekday filtering
- [x] **Calendar view data**
  - [x] Monthly price heatmap data
  - [x] Cheapest day per week
  - [x] Price trend indicators
- [x] **Smart suggestions**
  - [x] "Cheapest nearby dates" feature
  - [x] Flexible departure + return combinations
  - [x] Weekend/weekday preference options
- [x] **MCP tools**
  - [x] `search_flexible_dates` - +/- N days search
  - [x] `search_weekend_flights` - Weekend-only flights
  - [x] `search_weekday_flights` - Specific weekday search
  - [x] `get_calendar_heatmap` - Monthly price heatmap
  - [x] `suggest_best_dates` - Smart date suggestions

### ✈️ Phase 7: Airline Filtering ✅
- [x] **Airline preferences**
  - [x] Include/exclude specific airlines
  - [x] Alliance filtering (Star Alliance, OneWorld, SkyTeam)
  - [x] Low-cost carrier options
- [x] **Aircraft preferences**
  - [x] Filter by aircraft type (wide-body only, etc.)
  - [x] Exclude regional jets/turboprops
- [x] **Loyalty program integration**
  - [x] Preferred airline prioritization
  - [x] Frequent flyer program database
- [x] **MCP tools**
  - [x] `search_airlines` - Find airline info
  - [x] `get_alliance_airlines` - List alliance members
  - [x] `filter_flights_by_airline` - Apply airline filters
  - [x] `get_low_cost_carriers` - List budget airlines
  - [x] `get_airline_info` - Get airline details

### 🌐 Phase 8: HTTP API (FastAPI)
- [ ] **REST API endpoints**
  - [ ] `POST /search` - Flight search
  - [ ] `GET /airports` - Airport lookup
  - [ ] `POST /compare` - Date comparison
  - [ ] `GET /health` - Health check
- [ ] **API features**
  - [ ] OpenAPI/Swagger documentation
  - [ ] API key authentication
  - [ ] Rate limiting middleware
  - [ ] Request/response logging
- [ ] **Deployment**
  - [ ] Docker container
  - [ ] Docker Compose with Redis cache
  - [ ] Kubernetes manifests
  - [ ] Cloud Run / Railway templates

### 💡 Future Ideas
- GraphQL API alternative
- Browser extension for price comparison
- Telegram/WhatsApp bot integration
- Machine learning price predictions

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
