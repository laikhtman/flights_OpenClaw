# HTTP API

Fast Flights includes a production-ready REST API built with FastAPI.

## Quick Start

### Installation

```bash
pip install fast-flights[api]
```

### Running the Server

```bash
# Using the CLI
fast-flights-api

# Or with uvicorn directly
uvicorn fast_flights.http_api:app --reload

# With custom host/port
uvicorn fast_flights.http_api:app --host 0.0.0.0 --port 8080
```

### Docker

```bash
# Build and run with Docker
docker build -t fast-flights-api .
docker run -p 8000:8000 fast-flights-api

# Or use Docker Compose (includes Redis cache)
docker-compose up -d
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Endpoints

### Core Endpoints

#### `GET /health`
Health check endpoint.

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-01-15T10:30:00",
  "features": {
    "flight_search": true,
    "airport_lookup": true,
    "date_comparison": true,
    "flexible_dates": true,
    "price_tracking": true,
    "airline_filtering": true
  }
}
```

#### `POST /search`
Search for flights.

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2025-06-15",
    "adults": 2,
    "seat_class": "economy"
  }'
```

Request body:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `origin` | string | Yes | Origin airport IATA code |
| `destination` | string | Yes | Destination airport IATA code |
| `departure_date` | string | Yes | Departure date (YYYY-MM-DD) |
| `return_date` | string | No | Return date for round-trip |
| `adults` | int | No | Number of adults (default: 1) |
| `children` | int | No | Number of children (default: 0) |
| `seat_class` | string | No | Seat class (default: "economy") |
| `max_stops` | int | No | Maximum stops (0-2) |

#### `GET /airports`
Search for airports.

```bash
curl "http://localhost:8000/airports?query=new%20york&limit=5"
```

Query parameters:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | City or airport name |
| `limit` | int | No | Max results (default: 10) |

#### `POST /compare`
Compare prices across multiple dates.

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "dates": ["2025-06-15", "2025-06-16", "2025-06-17"]
  }'
```

### Flexible Date Endpoints

#### `POST /flexible-search`
Search with flexible dates (+/- N days).

```bash
curl -X POST http://localhost:8000/flexible-search \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2025-06-15",
    "days_before": 3,
    "days_after": 3
  }'
```

#### `GET /weekend-flights`
Search for weekend flights.

```bash
curl "http://localhost:8000/weekend-flights?origin=JFK&destination=LAX&start_date=2025-06-01&num_weekends=4"
```

#### `POST /calendar-heatmap`
Get a monthly price calendar.

```bash
curl -X POST http://localhost:8000/calendar-heatmap \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "year": 2025,
    "month": 6
  }'
```

### Price Tracking Endpoints

#### `POST /track`
Start tracking a route.

```bash
curl -X POST "http://localhost:8000/track?origin=JFK&destination=LAX&departure_date=2025-06-15"
```

#### `GET /price-history`
Get historical prices.

```bash
curl "http://localhost:8000/price-history?origin=JFK&destination=LAX&days=30"
```

#### `POST /alerts`
Set a price alert.

```bash
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2025-06-15",
    "target_price": 300,
    "webhook_url": "https://your-webhook.com/alert"
  }'
```

#### `GET /tracked-routes`
List all tracked routes.

```bash
curl "http://localhost:8000/tracked-routes?active_only=true"
```

### Airline Endpoints

#### `GET /airlines/search`
Search for airline information.

```bash
curl "http://localhost:8000/airlines/search?query=united"
```

#### `GET /airlines/{code}`
Get airline details by IATA code.

```bash
curl http://localhost:8000/airlines/UA
```

#### `GET /alliances/{alliance}`
Get all airlines in an alliance.

```bash
curl http://localhost:8000/alliances/star_alliance
```

#### `GET /airlines/low-cost/list`
Get all low-cost carriers.

```bash
curl http://localhost:8000/airlines/low-cost/list
```

#### `POST /filter-flights`
Filter flight results by airline preferences.

```bash
curl -X POST http://localhost:8000/filter-flights \
  -H "Content-Type: application/json" \
  -d '{
    "flights": [...],
    "alliances": ["star_alliance"],
    "exclude_low_cost": true
  }'
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FAST_FLIGHTS_API_KEY` | (none) | API key for authentication (optional) |
| `FAST_FLIGHTS_RATE_LIMIT` | 60 | Requests per minute per IP |
| `FAST_FLIGHTS_CORS_ORIGINS` | * | Comma-separated CORS origins |
| `PORT` | 8000 | Server port |
| `DEBUG` | false | Enable debug mode |

### Authentication

When `FAST_FLIGHTS_API_KEY` is set, all endpoints require authentication:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/search
```

### Rate Limiting

Default rate limit is 60 requests per minute per IP address. The response includes headers:

```
X-RateLimit-Remaining: 55
```

When exceeded, returns HTTP 429 Too Many Requests.

## Docker Deployment

### Basic Docker

```bash
# Build
docker build -t fast-flights-api .

# Run
docker run -p 8000:8000 \
  -e FAST_FLIGHTS_API_KEY=your-secret-key \
  -e FAST_FLIGHTS_RATE_LIMIT=100 \
  fast-flights-api
```

### Docker Compose

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env

# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Production Tips

1. **Set an API key** for authentication
2. **Use HTTPS** with a reverse proxy (nginx, traefik)
3. **Configure CORS** for your frontend domains
4. **Adjust rate limits** based on your needs
5. **Use health checks** for load balancers

## Example: Python Client

```python
import httpx

API_URL = "http://localhost:8000"
API_KEY = "your-api-key"  # if authentication enabled

def search_flights(origin: str, destination: str, date: str):
    response = httpx.post(
        f"{API_URL}/search",
        headers={"X-API-Key": API_KEY} if API_KEY else {},
        json={
            "origin": origin,
            "destination": destination,
            "departure_date": date,
        },
    )
    response.raise_for_status()
    return response.json()

# Usage
flights = search_flights("JFK", "LAX", "2025-06-15")
print(f"Found {flights['total_flights']} flights")
print(f"Cheapest: ${flights['best_price']}")
```

## Example: JavaScript/TypeScript

```typescript
const API_URL = "http://localhost:8000";
const API_KEY = "your-api-key";

async function searchFlights(
  origin: string,
  destination: string,
  date: string
) {
  const response = await fetch(`${API_URL}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY && { "X-API-Key": API_KEY }),
    },
    body: JSON.stringify({
      origin,
      destination,
      departure_date: date,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  return response.json();
}

// Usage
const flights = await searchFlights("JFK", "LAX", "2025-06-15");
console.log(`Found ${flights.total_flights} flights`);
```
