"""
Core flight search functionality.

This module provides the main functions for searching flights on Google Flights.
It supports multiple fetch modes for reliability and different data sources for parsing.

For AI agent integration, consider using the simplified API in `fast_flights.agent_api`.

Main Functions:
    - get_flights(): High-level function with convenient parameters
    - get_flights_from_filter(): Lower-level function using TFSData filter
    - parse_response(): Parse flight data from HTTP response

Fetch Modes:
    - "common": Direct HTTP request (fastest, may be blocked by Google)
    - "fallback": Try common first, fall back to playwright if blocked
    - "force-fallback": Always use remote playwright service
    - "local": Use local playwright installation (requires playwright package)
    - "bright-data": Use Bright Data SERP API (requires API key)

Example:
    >>> from fast_flights import get_flights, FlightData, Passengers
    >>> result = get_flights(
    ...     flight_data=[FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")],
    ...     trip="one-way",
    ...     seat="economy",
    ...     adults=2
    ... )
    >>> print(f"Found {len(result.flights)} flights")
"""

import re
import json
from typing import List, Literal, Optional, Union

from selectolax.lexbor import LexborHTMLParser, LexborNode

from .decoder import DecodedResult, ResultDecoder
from .schema import Flight, Result
from .flights_impl import FlightData, Passengers
from .filter import TFSData
from .fallback_playwright import fallback_playwright_fetch
from .bright_data_fetch import bright_data_fetch
from .primp import Client, Response


DataSource = Literal['html', 'js']
"""Type alias for data source: 'html' for HTML parsing, 'js' for JavaScript data extraction."""

# Default cookies embedded into the app to help bypass common consent gating.
# These are used only if the caller does not supply cookies (binary) and
# does not provide cookies via request_kwargs.
_DEFAULT_COOKIES = {
    "CONSENT": "PENDING+987",
    "SOCS": "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmRlIAEaBgiAo_CmBg",
}
_DEFAULT_COOKIES_BYTES = json.dumps(_DEFAULT_COOKIES).encode("utf-8")


def fetch(params: dict, request_kwargs: dict | None = None) -> Response:
    """
    Make a direct HTTP request to Google Flights.
    
    This is the fastest method but may be blocked by Google's bot detection.
    For more reliable results, use fetch_mode="fallback" in get_flights().
    
    Args:
        params: URL query parameters including 'tfs' (the encoded search filter)
        request_kwargs: Additional kwargs passed to the HTTP client (headers, cookies, etc.)
        
    Returns:
        Response object from the HTTP client
        
    Raises:
        AssertionError: If the response status code is not 200
    """
    client = Client(impersonate="chrome_126", verify=False)
    # Pass through any extra request kwargs (e.g., cookies, headers)
    req_kwargs = request_kwargs.copy() if request_kwargs else {}
    res = client.get("https://www.google.com/travel/flights", params=params, **req_kwargs)
    assert res.status_code == 200, f"{res.status_code} Result: {res.text_markdown}"
    return res


def _merge_binary_cookies(cookies_bytes: bytes | None, request_kwargs: dict | None) -> dict:
    """Parse binary cookies into request kwargs.

    Supported formats (in order):
    - JSON bytes -> dict or list of pairs
    - Pickle bytes -> dict
    - Raw cookie header bytes -> sets the 'Cookie' header

    Existing request_kwargs are copied and updated; existing 'cookies' or 'headers' are overridden by parsed values.
    """
    req_kwargs = request_kwargs.copy() if request_kwargs else {}
    if not cookies_bytes:
        return req_kwargs

    # Try JSON first
    try:
        s = cookies_bytes.decode("utf-8")
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            req_kwargs['cookies'] = parsed
            return req_kwargs
        if isinstance(parsed, list):
            # list of pairs
            try:
                req_kwargs['cookies'] = dict(parsed)
                return req_kwargs
            except Exception:
                pass
    except Exception:
        pass

    # Try pickle
    try:
        import pickle

        parsed = pickle.loads(cookies_bytes)
        if isinstance(parsed, dict):
            req_kwargs['cookies'] = parsed
            return req_kwargs
    except Exception:
        pass

    # Fallback: treat as raw Cookie header
    try:
        s = cookies_bytes.decode("utf-8")
        headers = req_kwargs.get('headers', {})
        # make a shallow copy to avoid mutating input
        headers = headers.copy() if isinstance(headers, dict) else {}
        headers['Cookie'] = s
        req_kwargs['headers'] = headers
    except Exception:
        # give up silently and return what we have
        pass

    return req_kwargs


def get_flights_from_filter(
    filter: TFSData,
    currency: str = "",
    *,
    mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "common",
    data_source: DataSource = 'html',
    cookies: bytes | None = None,
    request_kwargs: dict | None = None,
    cookie_consent: bool = True,
) -> Union[Result, DecodedResult, None]:
    """
    Search for flights using a pre-built TFSData filter.
    
    This is the lower-level search function. For most use cases, prefer
    get_flights() which provides a more convenient interface.
    
    For AI agent integration, use search_flights() from fast_flights.agent_api.
    
    Args:
        filter: TFSData object containing the encoded search parameters.
            Create with create_filter() or TFSData.from_interface().
        currency: Currency code for prices (e.g., "USD", "EUR"). Empty for default.
        mode: Fetch strategy:
            - "common": Direct HTTP request (fastest, may be blocked)
            - "fallback": Try common first, fall back to playwright if blocked
            - "force-fallback": Always use remote playwright service
            - "local": Use local playwright (requires playwright package)
            - "bright-data": Use Bright Data SERP API (requires BRIGHT_DATA_API_KEY env var)
        data_source: How to parse the response:
            - "html": Parse flight data from HTML (more fields, may break with changes)
            - "js": Extract from embedded JavaScript (more stable, fewer fields)
        cookies: Custom cookies as bytes. Supports:
            - JSON bytes: {"name": "value"}
            - Pickle bytes: pickled dict
            - Raw string: Cookie header value
        request_kwargs: Additional kwargs for HTTP client (headers, timeout, etc.)
        cookie_consent: If True and no cookies provided, use embedded consent cookies.
            Set to False if you handle cookies yourself.
    
    Returns:
        Result: When data_source="html", contains current_price and flights list.
        DecodedResult: When data_source="js", contains best and other flight lists.
        None: If no flights found and parsing fails gracefully.
        
    Raises:
        RuntimeError: If no flights found in the response.
        AssertionError: If HTTP request fails without fallback mode.
        
    Example:
        >>> from fast_flights import create_filter, get_flights_from_filter, FlightData, Passengers
        >>> filter = create_filter(
        ...     flight_data=[FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")],
        ...     trip="one-way",
        ...     passengers=Passengers(adults=1),
        ...     seat="economy"
        ... )
        >>> result = get_flights_from_filter(filter, mode="fallback")
        >>> print(result.flights[0].price)
    """
    data = filter.as_b64()

    params = {
        "tfs": data.decode("utf-8"),
        "hl": "en",
        "tfu": "EgQIABABIgA",
        "curr": currency,
    }

    # If the caller didn't provide cookies bytes and there is no cookies or Cookie header
    # in request_kwargs, use the embedded default cookies bytes (only when enabled).
    if cookies is None and cookie_consent:
        has_cookies_in_req = False
        if request_kwargs:
            if 'cookies' in request_kwargs:
                has_cookies_in_req = True
            elif 'headers' in request_kwargs and isinstance(request_kwargs['headers'], dict) and 'Cookie' in request_kwargs['headers']:
                has_cookies_in_req = True
        if not has_cookies_in_req:
            cookies = _DEFAULT_COOKIES_BYTES

    # Merge binary cookies into request kwargs (binary cookies take precedence)
    req_kwargs = _merge_binary_cookies(cookies, request_kwargs)

    if mode in {"common", "fallback"}:
        try:
            res = fetch(params, request_kwargs=req_kwargs)
        except AssertionError as e:
            if mode == "fallback":
                res = fallback_playwright_fetch(params, request_kwargs=req_kwargs)
            else:
                raise e

    elif mode == "local":
        from .local_playwright import local_playwright_fetch

        res = local_playwright_fetch(params, request_kwargs=req_kwargs)

    elif mode == "bright-data":
        res = bright_data_fetch(params, request_kwargs=req_kwargs)

    else:
        res = fallback_playwright_fetch(params, request_kwargs=req_kwargs)

    try:
        return parse_response(res, data_source)
    except RuntimeError as e:
        if mode == "fallback":
            return get_flights_from_filter(filter, mode="force-fallback", request_kwargs=req_kwargs, cookies=None, cookie_consent=cookie_consent)
        raise e



def get_flights(
    *,
    flight_data: List[FlightData],
    trip: Literal["round-trip", "one-way", "multi-city"],
    passengers: Optional[Passengers] = None,
    # Convenience passenger counters (used when `passengers` is None)
    adults: Optional[int] = None,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    seat: Literal["economy", "premium-economy", "business", "first"] = "economy",
    fetch_mode: Literal["common", "fallback", "force-fallback", "local", "bright-data"] = "common",
    max_stops: Optional[int] = None,
    data_source: DataSource = 'html',
    cookies: bytes | None = None,
    request_kwargs: dict | None = None,
    cookie_consent: bool = True,
) -> Union[Result, DecodedResult, None]:
    """
    Search for flights on Google Flights.
    
    This is the main entry point for flight searches. It provides a convenient
    interface with sensible defaults. For AI agent integration, consider using
    search_flights() from fast_flights.agent_api which returns structured responses.
    
    Args:
        flight_data: List of FlightData objects specifying routes and dates.
            For one-way: single FlightData with departure info.
            For round-trip: two FlightData objects (outbound and return).
        trip: Trip type - "one-way", "round-trip", or "multi-city".
            Note: "multi-city" is not fully supported yet.
        passengers: Passengers object specifying passenger counts.
            If None, uses the individual passenger count arguments below.
        adults: Number of adult passengers (default: 1 if passengers is None).
        children: Number of child passengers aged 2-11 (default: 0).
        infants_in_seat: Number of infants with own seat (default: 0).
        infants_on_lap: Number of lap infants under 2 (default: 0).
        seat: Seat class - "economy", "premium-economy", "business", or "first".
        fetch_mode: HTTP fetching strategy:
            - "common": Direct request (fastest, may be blocked by Google)
            - "fallback": Try common first, fall back to playwright if blocked (recommended)
            - "force-fallback": Always use remote playwright service
            - "local": Use local playwright installation (requires playwright)
            - "bright-data": Use Bright Data SERP API (requires BRIGHT_DATA_API_KEY)
        max_stops: Maximum number of stops (0=nonstop, 1, 2, or None for any).
        data_source: How to parse the response:
            - "html": Parse from HTML (more fields like is_best, delay)
            - "js": Extract from JavaScript (more stable but fewer fields)
        cookies: Custom cookies as bytes (JSON, pickle, or raw Cookie header).
        request_kwargs: Additional kwargs for HTTP client (headers, timeout, etc.).
        cookie_consent: Use embedded consent cookies if no cookies provided.
    
    Returns:
        Result: When data_source="html", with current_price and flights list.
        DecodedResult: When data_source="js", with best and other flight lists.
        None: If no flights found (in some cases).
    
    Raises:
        RuntimeError: If no flights found in the response.
        AssertionError: If HTTP request fails and no fallback available.
    
    Example:
        One-way flight:
        >>> result = get_flights(
        ...     flight_data=[FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX")],
        ...     trip="one-way",
        ...     seat="economy",
        ...     adults=2,
        ...     fetch_mode="fallback"
        ... )
        >>> print(f"Price level: {result.current_price}")
        >>> print(f"Cheapest: {result.flights[0].price}")
        
        Round-trip flight:
        >>> result = get_flights(
        ...     flight_data=[
        ...         FlightData(date="2025-06-15", from_airport="JFK", to_airport="LAX"),
        ...         FlightData(date="2025-06-22", from_airport="LAX", to_airport="JFK")
        ...     ],
        ...     trip="round-trip",
        ...     seat="business",
        ...     passengers=Passengers(adults=1, children=1)
        ... )
    """
    # If the caller didn't supply a Passengers object, build one from the
    # convenience counters. Default to 1 adult when no adults count provided
    # (matches previous typical usage where at least one adult is expected).
    if passengers is None:
        ad = 1 if adults is None else adults
        passengers = Passengers(
            adults=ad,
            children=children,
            infants_in_seat=infants_in_seat,
            infants_on_lap=infants_on_lap,
        )

    tfs: TFSData = TFSData.from_interface(
        flight_data=flight_data,
        trip=trip,
        passengers=passengers,
        seat=seat,
        max_stops=max_stops,
    )

    return get_flights_from_filter(
        tfs,
        mode=fetch_mode,
        data_source=data_source,
        cookies=cookies,
        request_kwargs=request_kwargs,
        cookie_consent=cookie_consent,
    )



def parse_response(
     r: Response,
     data_source: DataSource,
     *,
     dangerously_allow_looping_last_item: bool = False,
 ) -> Union[Result, DecodedResult, None]:
    """
    Parse flight data from an HTTP response.
    
    This function extracts flight information from the Google Flights response.
    It supports two parsing modes: HTML parsing and JavaScript data extraction.
    
    Args:
        r: Response object from the HTTP client.
        data_source: Parsing method:
            - "html": Parse from HTML DOM (more fields like is_best, delay)
            - "js": Extract from embedded JavaScript data (more stable)
        dangerously_allow_looping_last_item: If True, includes the last item
            in non-best flight lists. Usually should be False to avoid
            parsing artifacts.
    
    Returns:
        Result: When data_source="html", contains:
            - current_price: "low", "typical", or "high"
            - flights: List of Flight objects with full details
        DecodedResult: When data_source="js", contains:
            - raw: The raw parsed data
            - best: List of best Itinerary objects
            - other: List of other Itinerary objects
        None: If data_source="js" and no data found.
    
    Raises:
        RuntimeError: If no flights found in the HTML response.
        AssertionError: If JavaScript data is malformed.
    
    Note:
        HTML parsing is more comprehensive but may break if Google changes
        their page structure. JavaScript parsing is more stable but provides
        fewer fields.
    """
    class _blank:
        def text(self, *_, **__):
            return ""

        def iter(self):
            return []

    blank = _blank()

    def safe(n: Optional[LexborNode]):
        return n or blank

    parser = LexborHTMLParser(r.text)

    if data_source == 'js':
        script = parser.css_first(r'script.ds\:1').text()

        match = re.search(r'^.*?\{.*?data:(\[.*\]).*}', script)
        assert match, 'Malformed js data, cannot find script data'
        data = json.loads(match.group(1))
        return ResultDecoder.decode(data) if data is not None else None

    flights = []

    for i, fl in enumerate(parser.css('div[jsname="IWWDBc"], div[jsname="YdtKid"]')):
        is_best_flight = i == 0

        for item in fl.css("ul.Rk10dc li")[
            : (None if dangerously_allow_looping_last_item or i == 0 else -1)
        ]:
            # Flight name
            name = safe(item.css_first("div.sSHqwe.tPgKwe.ogfYpf span")).text(
                strip=True
            )

            # Get departure & arrival time
            dp_ar_node = item.css("span.mv1WYe div")
            try:
                departure_time = dp_ar_node[0].text(strip=True)
                arrival_time = dp_ar_node[1].text(strip=True)
            except IndexError:
                # sometimes this is not present
                departure_time = ""
                arrival_time = ""

            # Get arrival time ahead
            time_ahead = safe(item.css_first("span.bOzv6")).text()

            # Get duration
            duration = safe(item.css_first("li div.Ak5kof div")).text()

            # Get flight stops
            stops = safe(item.css_first(".BbR8Ec .ogfYpf")).text()

            # Get delay
            delay = safe(item.css_first(".GsCCve")).text() or None

            # Get prices
            price = safe(item.css_first(".YMlIz.FpEdX")).text() or "0"

            # Stops formatting
            try:
                stops_fmt = 0 if stops == "Nonstop" else int(stops.split(" ", 1)[0])
            except ValueError:
                stops_fmt = "Unknown"

            flights.append(
                {
                    "is_best": is_best_flight,
                    "name": name,
                    "departure": " ".join(departure_time.split()),
                    "arrival": " ".join(arrival_time.split()),
                    "arrival_time_ahead": time_ahead,
                    "duration": duration,
                    "stops": stops_fmt,
                    "delay": delay,
                    "price": price.replace(",", ""),
                }
            )

    current_price = safe(parser.css_first("span.gOatQ")).text()
    if not flights:
        raise RuntimeError("No flights found:\n{}".format(r.text_markdown))

    return Result(current_price=current_price, flights=[Flight(**fl) for fl in flights])  # type: ignore