"""
Price tracker module for monitoring flight prices.

Provides background price monitoring, change detection, and alert triggering.
"""

import logging
import threading
import time
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from .price_storage import (
    PriceRecord,
    PriceAlert,
    TrackedRoute,
    PriceStorageBackend,
    get_price_storage,
)

try:
    from .agent_api import search_flights
    from .schema import FlightSearchResult
    AGENT_API_AVAILABLE = True
except ImportError:
    AGENT_API_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# Price Change Detection
# ============================================================================

class PriceChange:
    """Represents a detected price change."""
    
    def __init__(
        self,
        route: TrackedRoute,
        old_price: Optional[float],
        new_price: float,
        change_amount: float,
        change_percent: float,
        price_level: Optional[str] = None,
    ):
        self.route = route
        self.old_price = old_price
        self.new_price = new_price
        self.change_amount = change_amount
        self.change_percent = change_percent
        self.price_level = price_level
        self.detected_at = datetime.now()
    
    @property
    def is_decrease(self) -> bool:
        """Check if price decreased."""
        return self.change_amount < 0
    
    @property
    def is_increase(self) -> bool:
        """Check if price increased."""
        return self.change_amount > 0
    
    @property
    def is_significant(self, threshold_percent: float = 5.0) -> bool:
        """Check if change is significant."""
        return abs(self.change_percent) >= threshold_percent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "route": self.route.to_dict(),
            "old_price": self.old_price,
            "new_price": self.new_price,
            "change_amount": self.change_amount,
            "change_percent": round(self.change_percent, 2),
            "price_level": self.price_level,
            "is_decrease": self.is_decrease,
            "detected_at": self.detected_at.isoformat(),
        }
    
    def format_message(self) -> str:
        """Format a human-readable message."""
        direction = "📉 dropped" if self.is_decrease else "📈 increased"
        route_str = f"{self.route.origin} → {self.route.destination}"
        
        if self.old_price:
            return (
                f"Price {direction} for {route_str} on {self.route.departure_date}: "
                f"${self.old_price:.0f} → ${self.new_price:.0f} "
                f"({self.change_percent:+.1f}%)"
            )
        else:
            return (
                f"New price for {route_str} on {self.route.departure_date}: "
                f"${self.new_price:.0f} ({self.price_level or 'unknown'} level)"
            )


# ============================================================================
# Alert Handlers
# ============================================================================

class AlertHandler:
    """Base class for alert handlers."""
    
    def send(self, alert: PriceAlert, price: float, message: str) -> bool:
        """Send an alert. Returns True if successful."""
        raise NotImplementedError


class WebhookAlertHandler(AlertHandler):
    """Send alerts via webhook (Discord, Slack, etc.)."""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def send(self, alert: PriceAlert, price: float, message: str) -> bool:
        """Send webhook alert."""
        if not alert.webhook_url:
            return False
        
        try:
            import urllib.request
            import json
            
            # Detect webhook type and format payload
            payload = self._format_payload(alert, price, message)
            
            req = urllib.request.Request(
                alert.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status in (200, 201, 204)
                
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False
    
    def _format_payload(
        self, alert: PriceAlert, price: float, message: str
    ) -> Dict[str, Any]:
        """Format webhook payload based on URL type."""
        url = alert.webhook_url or ""
        route_str = f"{alert.origin} → {alert.destination}"
        
        # Discord webhook
        if "discord.com/api/webhooks" in url:
            return {
                "embeds": [{
                    "title": "✈️ Flight Price Alert!",
                    "description": message,
                    "color": 0x00FF00,  # Green
                    "fields": [
                        {"name": "Route", "value": route_str, "inline": True},
                        {"name": "Date", "value": alert.departure_date, "inline": True},
                        {"name": "Current Price", "value": f"${price:.0f}", "inline": True},
                        {"name": "Target Price", "value": f"${alert.target_price:.0f}", "inline": True},
                    ],
                    "timestamp": datetime.now().isoformat(),
                }]
            }
        
        # Slack webhook
        if "hooks.slack.com" in url:
            return {
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "✈️ Flight Price Alert!"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": message}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Route:* {route_str}"},
                            {"type": "mrkdwn", "text": f"*Date:* {alert.departure_date}"},
                            {"type": "mrkdwn", "text": f"*Current:* ${price:.0f}"},
                            {"type": "mrkdwn", "text": f"*Target:* ${alert.target_price:.0f}"},
                        ]
                    }
                ]
            }
        
        # Generic webhook
        return {
            "type": "flight_price_alert",
            "message": message,
            "route": route_str,
            "departure_date": alert.departure_date,
            "current_price": price,
            "target_price": alert.target_price,
            "currency": alert.currency,
            "timestamp": datetime.now().isoformat(),
        }


class EmailAlertHandler(AlertHandler):
    """Send alerts via email (SMTP)."""
    
    def __init__(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email or smtp_user
    
    def send(self, alert: PriceAlert, price: float, message: str) -> bool:
        """Send email alert."""
        if not alert.email or not self.smtp_user or not self.smtp_password:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            route_str = f"{alert.origin} → {alert.destination}"
            
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"✈️ Flight Price Alert: {route_str} - ${price:.0f}"
            msg["From"] = self.from_email
            msg["To"] = alert.email
            
            # Plain text
            text = f"""
Flight Price Alert!

{message}

Route: {route_str}
Date: {alert.departure_date}
Current Price: ${price:.0f}
Target Price: ${alert.target_price:.0f}

Book soon before prices change!
            """
            
            # HTML
            html = f"""
<html>
<body>
<h2>✈️ Flight Price Alert!</h2>
<p>{message}</p>
<table>
<tr><td><strong>Route:</strong></td><td>{route_str}</td></tr>
<tr><td><strong>Date:</strong></td><td>{alert.departure_date}</td></tr>
<tr><td><strong>Current Price:</strong></td><td style="color: green; font-weight: bold;">${price:.0f}</td></tr>
<tr><td><strong>Target Price:</strong></td><td>${alert.target_price:.0f}</td></tr>
</table>
<p><em>Book soon before prices change!</em></p>
</body>
</html>
            """
            
            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(html, "html"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, alert.email, msg.as_string())
            
            return True
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False


class CallbackAlertHandler(AlertHandler):
    """Send alerts via callback function."""
    
    def __init__(self, callback: Callable[[PriceAlert, float, str], None]):
        self.callback = callback
    
    def send(self, alert: PriceAlert, price: float, message: str) -> bool:
        """Send callback alert."""
        try:
            self.callback(alert, price, message)
            return True
        except Exception as e:
            logger.error(f"Callback alert failed: {e}")
            return False


# ============================================================================
# Price Tracker
# ============================================================================

class PriceTracker:
    """
    Flight price tracker with background monitoring.
    
    Example:
        >>> tracker = PriceTracker()
        >>> 
        >>> # Track a route
        >>> route_id = tracker.track_route(
        ...     origin="JFK",
        ...     destination="LAX", 
        ...     departure_date="2025-06-15",
        ...     check_interval_minutes=30,
        ... )
        >>> 
        >>> # Set a price alert
        >>> alert_id = tracker.set_alert(
        ...     origin="JFK",
        ...     destination="LAX",
        ...     departure_date="2025-06-15",
        ...     target_price=250,
        ...     webhook_url="https://discord.com/api/webhooks/...",
        ... )
        >>> 
        >>> # Start background monitoring
        >>> tracker.start()
        >>> 
        >>> # ... later ...
        >>> tracker.stop()
    """
    
    def __init__(
        self,
        storage: Optional[PriceStorageBackend] = None,
        check_interval_seconds: int = 60,
        fetch_mode: str = "fallback",
    ):
        """
        Initialize the price tracker.
        
        Args:
            storage: Price storage backend (default: SQLite)
            check_interval_seconds: How often to check for routes due (default: 60s)
            fetch_mode: Fetch mode for flight searches (default: "fallback")
        """
        self.storage = storage or get_price_storage()
        self.check_interval = check_interval_seconds
        self.fetch_mode = fetch_mode
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Alert handlers
        self._webhook_handler = WebhookAlertHandler()
        self._email_handler: Optional[EmailAlertHandler] = None
        self._callback_handlers: List[CallbackAlertHandler] = []
        
        # Callbacks for price changes
        self._on_price_change: List[Callable[[PriceChange], None]] = []
    
    def configure_email(
        self,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        from_email: Optional[str] = None,
    ):
        """Configure email alerts."""
        self._email_handler = EmailAlertHandler(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_email=from_email,
        )
    
    def on_price_change(self, callback: Callable[[PriceChange], None]):
        """Register a callback for price changes."""
        self._on_price_change.append(callback)
    
    def on_alert(self, callback: Callable[[PriceAlert, float, str], None]):
        """Register a callback for alerts."""
        self._callback_handlers.append(CallbackAlertHandler(callback))
    
    # ========================================================================
    # Route Tracking
    # ========================================================================
    
    def track_route(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        seat_class: str = "economy",
        adults: int = 1,
        check_interval_minutes: int = 60,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Start tracking a route for price changes.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Return date for round-trip
            seat_class: Seat class
            adults: Number of adults
            check_interval_minutes: How often to check prices
            metadata: Additional metadata
            
        Returns:
            Route ID
        """
        route = TrackedRoute(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            trip_type="round-trip" if return_date else "one-way",
            seat_class=seat_class,
            adults=adults,
            check_interval_minutes=check_interval_minutes,
            is_active=True,
            created_at=datetime.now(),
            metadata=metadata or {},
        )
        return self.storage.save_tracked_route(route)
    
    def untrack_route(self, route_id: int) -> bool:
        """Stop tracking a route."""
        return self.storage.delete_tracked_route(route_id)
    
    def pause_route(self, route_id: int) -> bool:
        """Pause tracking a route."""
        return self.storage.update_tracked_route(route_id, is_active=False)
    
    def resume_route(self, route_id: int) -> bool:
        """Resume tracking a route."""
        return self.storage.update_tracked_route(route_id, is_active=True)
    
    def get_tracked_routes(self, active_only: bool = True) -> List[TrackedRoute]:
        """Get all tracked routes."""
        return self.storage.get_tracked_routes(active_only=active_only)
    
    # ========================================================================
    # Price Alerts
    # ========================================================================
    
    def set_alert(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        target_price: float,
        return_date: Optional[str] = None,
        seat_class: str = "economy",
        adults: int = 1,
        webhook_url: Optional[str] = None,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Set a price alert.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            target_price: Alert when price <= this amount
            return_date: Return date for round-trip
            seat_class: Seat class
            adults: Number of adults
            webhook_url: Webhook URL for notifications
            email: Email address for notifications
            metadata: Additional metadata
            
        Returns:
            Alert ID
        """
        alert = PriceAlert(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            return_date=return_date,
            trip_type="round-trip" if return_date else "one-way",
            seat_class=seat_class,
            adults=adults,
            target_price=target_price,
            webhook_url=webhook_url,
            email=email,
            is_active=True,
            created_at=datetime.now(),
            metadata=metadata or {},
        )
        return self.storage.save_alert(alert)
    
    def remove_alert(self, alert_id: int) -> bool:
        """Remove a price alert."""
        return self.storage.delete_alert(alert_id)
    
    def get_alerts(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get all alerts."""
        return self.storage.get_alerts(
            origin=origin.upper() if origin else None,
            destination=destination.upper() if destination else None,
            active_only=active_only,
        )
    
    # ========================================================================
    # Price History
    # ========================================================================
    
    def get_price_history(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[PriceRecord]:
        """Get price history for a route."""
        return self.storage.get_price_history(
            origin=origin.upper(),
            destination=destination.upper(),
            departure_date=departure_date,
            days=days,
            limit=limit,
        )
    
    def get_price_stats(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get price statistics for a route."""
        if hasattr(self.storage, "get_price_stats"):
            return self.storage.get_price_stats(
                origin=origin.upper(),
                destination=destination.upper(),
                departure_date=departure_date,
                days=days,
            )
        
        # Fallback: compute stats from history
        history = self.get_price_history(origin, destination, departure_date, days)
        if not history:
            return {
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "record_count": 0,
                "days_analyzed": days,
            }
        
        prices = [r.price for r in history]
        return {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "record_count": len(prices),
            "days_analyzed": days,
        }
    
    # ========================================================================
    # Manual Price Check
    # ========================================================================
    
    def check_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        seat_class: str = "economy",
        adults: int = 1,
        save: bool = True,
    ) -> Optional[PriceRecord]:
        """
        Check the current price for a route.
        
        Args:
            origin: Origin airport code
            destination: Destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            return_date: Return date for round-trip
            seat_class: Seat class
            adults: Number of adults
            save: Whether to save the price to history
            
        Returns:
            PriceRecord if successful, None otherwise
        """
        if not AGENT_API_AVAILABLE:
            logger.error("Agent API not available. Install with: pip install fast-flights[agent]")
            return None
        
        try:
            result = search_flights({
                "origin": origin.upper(),
                "destination": destination.upper(),
                "departure_date": departure_date,
                "return_date": return_date,
                "seat_class": seat_class,
                "adults": adults,
            })
            
            if not result.success or not result.flights:
                logger.warning(f"No flights found for {origin} → {destination}")
                return None
            
            # Get cheapest price
            best_flight = result.flights[0]
            price = self._parse_price(best_flight.price)
            
            record = PriceRecord(
                origin=origin.upper(),
                destination=destination.upper(),
                departure_date=departure_date,
                return_date=return_date,
                trip_type="round-trip" if return_date else "one-way",
                seat_class=seat_class,
                adults=adults,
                price=price,
                airline=best_flight.name,
                price_level=result.current_price,
                recorded_at=datetime.now(),
            )
            
            if save:
                record.id = self.storage.save_price(record)
            
            return record
            
        except Exception as e:
            logger.error(f"Price check failed: {e}")
            return None
    
    def _parse_price(self, price_str: str) -> float:
        """Parse price string to float."""
        # Remove currency symbols and commas
        match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
        return float(match.group()) if match else 0.0
    
    # ========================================================================
    # Background Monitoring
    # ========================================================================
    
    def start(self):
        """Start background price monitoring."""
        if self._running:
            logger.warning("Tracker already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("Price tracker started")
    
    def stop(self, timeout: float = 5.0):
        """Stop background price monitoring."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=timeout)
        
        logger.info("Price tracker stopped")
    
    def is_running(self) -> bool:
        """Check if tracker is running."""
        return self._running
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self._check_due_routes()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
            
            # Wait for next check interval
            self._stop_event.wait(self.check_interval)
    
    def _check_due_routes(self):
        """Check routes that are due for price check."""
        routes = self.storage.get_routes_due_for_check()
        
        for route in routes:
            if self._stop_event.is_set():
                break
            
            try:
                self._check_route(route)
            except Exception as e:
                logger.error(f"Route check failed for {route.origin}-{route.destination}: {e}")
    
    def _check_route(self, route: TrackedRoute):
        """Check a single route for price changes."""
        record = self.check_price(
            origin=route.origin,
            destination=route.destination,
            departure_date=route.departure_date,
            return_date=route.return_date,
            seat_class=route.seat_class,
            adults=route.adults,
            save=True,
        )
        
        if not record:
            return
        
        # Update route with last check info
        self.storage.update_tracked_route(
            route.id,
            last_checked=datetime.now(),
            last_price=record.price,
        )
        
        # Detect price change
        if route.last_price is not None:
            change_amount = record.price - route.last_price
            change_percent = (change_amount / route.last_price) * 100 if route.last_price > 0 else 0
            
            change = PriceChange(
                route=route,
                old_price=route.last_price,
                new_price=record.price,
                change_amount=change_amount,
                change_percent=change_percent,
                price_level=record.price_level,
            )
            
            # Notify callbacks
            for callback in self._on_price_change:
                try:
                    callback(change)
                except Exception as e:
                    logger.error(f"Price change callback failed: {e}")
        
        # Check alerts
        self._check_alerts_for_route(route, record.price)
    
    def _check_alerts_for_route(self, route: TrackedRoute, current_price: float):
        """Check if any alerts should trigger for this route."""
        alerts = self.storage.get_alerts(
            origin=route.origin,
            destination=route.destination,
            active_only=True,
        )
        
        for alert in alerts:
            if alert.departure_date != route.departure_date:
                continue
            
            if current_price <= alert.target_price:
                self._trigger_alert(alert, current_price)
    
    def _trigger_alert(self, alert: PriceAlert, current_price: float):
        """Trigger a price alert."""
        message = (
            f"Price alert triggered! {alert.origin} → {alert.destination} "
            f"on {alert.departure_date} is now ${current_price:.0f} "
            f"(target: ${alert.target_price:.0f})"
        )
        
        logger.info(message)
        
        # Send webhook
        if alert.webhook_url:
            self._webhook_handler.send(alert, current_price, message)
        
        # Send email
        if alert.email and self._email_handler:
            self._email_handler.send(alert, current_price, message)
        
        # Callback handlers
        for handler in self._callback_handlers:
            handler.send(alert, current_price, message)
        
        # Mark alert as triggered (deactivate)
        self.storage.update_alert(
            alert.id,
            is_active=False,
            triggered_at=datetime.now(),
        )


# ============================================================================
# Global Tracker Instance
# ============================================================================

_tracker: Optional[PriceTracker] = None
_tracker_lock = threading.Lock()


def get_price_tracker(**kwargs) -> PriceTracker:
    """
    Get the global price tracker instance.
    
    Args:
        **kwargs: Configuration for PriceTracker
        
    Returns:
        PriceTracker instance
    """
    global _tracker
    
    with _tracker_lock:
        if _tracker is None:
            _tracker = PriceTracker(**kwargs)
        return _tracker


def reset_price_tracker():
    """Reset the global tracker instance (for testing)."""
    global _tracker
    with _tracker_lock:
        if _tracker is not None:
            _tracker.stop()
            _tracker = None
