# 🔧 MCP Server

The MCP (Model Context Protocol) server allows AI agents like **OpenClaw**, **Claude Desktop**, and other MCP-compatible clients to use fast-flights as a tool.

[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)
[![OpenClaw Ready](https://img.shields.io/badge/OpenClaw-Ready-orange.svg)](https://openclaw.io)

---

## Installation

```bash
pip install fast-flights[mcp]
```

---

## Quick Start

### Run the Server

```bash
# Using the installed script
fast-flights-mcp

# Or using Python module
python -m fast_flights.mcp_server
```

---

## Configuration

### 🦎 OpenClaw

Add to your OpenClaw server configuration:

```json
{
    "servers": [
        {
            "name": "fast-flights",
            "type": "stdio",
            "command": "python",
            "args": ["-m", "fast_flights.mcp_server"]
        }
    ]
}
```

### 🤖 Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

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

### ⚙️ Custom MCP Clients

The server uses stdio transport. Connect to it by spawning the process and communicating via stdin/stdout.

---

## 🛠️ Available Tools

### ✈️ `search_flights`

Search for flights between airports.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code (e.g., "JFK") |
| `destination` | string | ✅ | Destination airport IATA code (e.g., "LAX") |
| `departure_date` | string | ✅ | Date in YYYY-MM-DD format |
| `return_date` | string | ❌ | Return date for round-trip |
| `adults` | integer | ❌ | Number of adults (default: 1) |
| `children` | integer | ❌ | Number of children (default: 0) |
| `seat_class` | string | ❌ | "economy", "premium-economy", "business", "first" |
| `max_stops` | integer | ❌ | Maximum stops (0=nonstop, 1, 2) |

**Example Response:**

```json
{
    "summary": "Found 12 flight option(s). Price level: low. Best option: Delta at $249...",
    "status": "success",
    "data": {
        "price_level": "low",
        "total_options": 12,
        "best_flight": {
            "name": "Delta",
            "price": "$249",
            "departure": "10:30 AM",
            "arrival": "1:45 PM",
            "duration": "5h 15m",
            "stops": 0
        },
        "all_flights": [...]
    }
}
```

---

### 🔍 `search_airport`

Find airport codes by name or city.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | ✅ | City or airport name to search |
| `limit` | integer | ❌ | Max results (default: 10) |

**Example Response:**

```json
{
    "query": "tokyo",
    "results": [
        {"code": "NRT", "name": "Tokyo Narita International Airport"},
        {"code": "HND", "name": "Tokyo Haneda Airport"}
    ],
    "total": 2,
    "hint": "Use the 'code' field as origin/destination in search_flights"
}
```

---

### `compare_flight_dates`

Compare prices across multiple dates.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport code |
| `destination` | string | ✅ | Destination airport code |
| `dates` | array | ✅ | List of dates (YYYY-MM-DD), 2-7 dates |
| `adults` | integer | ❌ | Number of adults (default: 1) |
| `seat_class` | string | ❌ | Seat class (default: "economy") |

**Example Response:**

```json
{
    "comparison": [
        {"date": "2025-06-15", "cheapest_price": "$289", "price_level": "typical"},
        {"date": "2025-06-16", "cheapest_price": "$249", "price_level": "low"},
        {"date": "2025-06-17", "cheapest_price": "$312", "price_level": "high"}
    ],
    "recommendation": "Best date to fly: 2025-06-16 at $249",
    "route": "JFK → LAX",
    "dates_searched": 3
}
```

---

## � Price Tracking Tools

### 📈 `track_price`

Start tracking a route for price changes.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `departure_date` | string | ✅ | Date in YYYY-MM-DD format |
| `return_date` | string | ❌ | Return date for round-trip |
| `seat_class` | string | ❌ | Seat class (default: "economy") |
| `check_interval_minutes` | integer | ❌ | Check frequency (default: 60) |

**Example Response:**

```json
{
    "status": "success",
    "message": "Now tracking JFK → LAX",
    "route_id": 1,
    "departure_date": "2025-06-15",
    "check_interval_minutes": 60,
    "current_price": 299.0,
    "price_level": "typical"
}
```

---

### 📜 `get_price_history`

Get historical prices for a route.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `departure_date` | string | ❌ | Specific date (omit for all) |
| `days` | integer | ❌ | Days of history (default: 7) |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "departure_date": "2025-06-15",
    "days_analyzed": 7,
    "statistics": {
        "min_price": 249.0,
        "max_price": 399.0,
        "avg_price": 312.5,
        "record_count": 24
    },
    "price_history": [
        {"price": 289.0, "price_level": "typical", "airline": "Delta", "recorded_at": "2025-02-03T10:30:00"},
        {"price": 299.0, "price_level": "typical", "airline": "United", "recorded_at": "2025-02-03T09:00:00"}
    ],
    "total_records": 24
}
```

---

### 🔔 `set_price_alert`

Set an alert when price drops below target.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `departure_date` | string | ✅ | Date in YYYY-MM-DD format |
| `target_price` | number | ✅ | Alert when price ≤ this |
| `webhook_url` | string | ❌ | Discord/Slack webhook URL |
| `email` | string | ❌ | Email address (needs SMTP) |

**Example Response:**

```json
{
    "status": "success",
    "message": "Alert set for JFK → LAX",
    "alert_id": 1,
    "target_price": 250,
    "current_price": 299.0,
    "will_trigger": false,
    "notification_method": "webhook"
}
```

---

### 📋 `get_tracked_routes`

List all tracked routes.

**Example Response:**

```json
{
    "total_routes": 2,
    "routes": [
        {
            "id": 1,
            "route": "JFK → LAX",
            "departure_date": "2025-06-15",
            "check_interval_minutes": 60,
            "is_active": true,
            "last_price": 299.0,
            "last_checked": "2025-02-03T10:30:00"
        }
    ]
}
```

---

### 📋 `get_price_alerts`

List all price alerts.

**Example Response:**

```json
{
    "total_alerts": 1,
    "alerts": [
        {
            "id": 1,
            "route": "JFK → LAX",
            "departure_date": "2025-06-15",
            "target_price": 250,
            "is_active": true,
            "has_webhook": true,
            "triggered_at": null
        }
    ]
}
```

---

## �🔧 Troubleshooting

### "MCP package not installed"

```bash
pip install fast-flights[mcp]
```

### "Pydantic package not installed"

The MCP server requires Pydantic. It should be installed automatically with `[mcp]`, but you can install manually:

```bash
pip install pydantic pydantic-settings
```

### Connection Issues

1. Make sure the server is running: `python -m fast_flights.mcp_server`
2. Check that your MCP client is configured to use stdio transport
3. Verify the Python path in your configuration

---

## 📋 Logging

The server logs to stderr. Set the log level via environment variable:

```bash
# More verbose logging
export FAST_FLIGHTS_LOG_LEVEL=DEBUG
python -m fast_flights.mcp_server
```
