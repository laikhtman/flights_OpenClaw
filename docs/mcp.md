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

## �️ Flexible Date Search Tools

### 📅 `search_flexible_dates`

Search for flights with flexible departure dates (+/- N days).

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `departure_date` | string | ✅ | Center date (YYYY-MM-DD) |
| `days_before` | integer | ❌ | Days before center (default: 3) |
| `days_after` | integer | ❌ | Days after center (default: 3) |
| `return_date` | string | ❌ | Return date for round-trip |
| `seat_class` | string | ❌ | Seat class (default: "economy") |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "base_date": "2025-06-15",
    "dates_searched": 7,
    "recommendation": "Fly on 2025-06-17 (Tuesday) to save $50 compared to 2025-06-14",
    "cheapest_date": {
        "date": "2025-06-17",
        "price": 249.0,
        "day_of_week": "Tuesday",
        "is_weekend": false
    },
    "average_price": 289.0
}
```

---

### 🗓️ `search_weekend_flights`

Search for weekend-only flights.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `start_date` | string | ✅ | Start searching from (YYYY-MM-DD) |
| `num_weekends` | integer | ❌ | Weekends to search (default: 4) |
| `seat_class` | string | ❌ | Seat class (default: "economy") |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "weekends_searched": 4,
    "recommendation": "Best price found: 2025-06-21 at $279",
    "cheapest_weekend": {
        "date": "2025-06-21",
        "price": 279.0,
        "day_of_week": "Saturday"
    },
    "average_price": 315.0
}
```

---

### 📆 `search_weekday_flights`

Search for flights on specific weekdays (often cheaper mid-week).

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `start_date` | string | ✅ | Start date (YYYY-MM-DD) |
| `weekdays` | array | ✅ | Days to search ("tuesday", "wednesday", etc.) |
| `num_weeks` | integer | ❌ | Weeks to search (default: 4) |
| `seat_class` | string | ❌ | Seat class (default: "economy") |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "weekdays_searched": ["tuesday", "wednesday"],
    "weeks_covered": 4,
    "recommendation": "Fly on 2025-06-17 (Tuesday) to save $80",
    "cheapest_day": {
        "date": "2025-06-17",
        "price": 219.0,
        "day_of_week": "Tuesday"
    },
    "average_price": 259.0
}
```

---

### 🗓️ `get_calendar_heatmap`

Get monthly calendar with price heatmap data.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `year` | integer | ✅ | Year (e.g., 2025) |
| `month` | integer | ✅ | Month (1-12) |
| `seat_class` | string | ❌ | Seat class (default: "economy") |
| `sample_days` | array | ❌ | Specific days to check (for speed) |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "month": "June 2025",
    "cheapest_day": {
        "date": "2025-06-17",
        "price": 219.0,
        "day_of_week": "Tuesday"
    },
    "cheapest_week": 3,
    "price_range": {"min": 219.0, "max": 450.0},
    "days": [
        {"date": "2025-06-01", "price": 289.0, "day_of_week": "Sunday", "is_weekend": true},
        {"date": "2025-06-02", "price": 249.0, "day_of_week": "Monday", "is_weekend": false}
    ]
}
```

---

### 💡 `suggest_best_dates`

Get smart suggestions for optimal travel dates.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `origin` | string | ✅ | Origin airport IATA code |
| `destination` | string | ✅ | Destination airport IATA code |
| `preferred_date` | string | ✅ | Preferred date (YYYY-MM-DD) |
| `flexibility_days` | integer | ❌ | Flexible range (default: 7) |
| `prefer_weekends` | boolean | ❌ | Only weekend suggestions |
| `avoid_weekends` | boolean | ❌ | Exclude weekends |
| `max_results` | integer | ❌ | Max suggestions (default: 5) |

**Example Response:**

```json
{
    "route": "JFK → LAX",
    "preferred_date": "2025-06-15",
    "flexibility": "+/- 7 days",
    "recommendation": "Best date: 2025-06-17 (Tuesday) at $219 - Save $150 vs worst date!",
    "suggestions": [
        {"rank": 1, "date": "2025-06-17", "day_of_week": "Tuesday", "price": 219.0},
        {"rank": 2, "date": "2025-06-18", "day_of_week": "Wednesday", "price": 229.0},
        {"rank": 3, "date": "2025-06-10", "day_of_week": "Tuesday", "price": 239.0}
    ],
    "average_price": 285.0
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
