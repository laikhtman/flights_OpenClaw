"""
Price storage module for flight price tracking.

Provides SQLite-based storage for historical flight prices with optional
Redis/PostgreSQL backends for production environments.
"""

import sqlite3
import json
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class PriceRecord:
    """A single price record for a flight route."""
    id: Optional[int] = None
    origin: str = ""
    destination: str = ""
    departure_date: str = ""  # YYYY-MM-DD
    return_date: Optional[str] = None  # YYYY-MM-DD for round-trip
    trip_type: str = "one-way"  # one-way, round-trip
    seat_class: str = "economy"
    adults: int = 1
    price: float = 0.0
    currency: str = "USD"
    airline: Optional[str] = None
    price_level: Optional[str] = None  # low, typical, high
    recorded_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "trip_type": self.trip_type,
            "seat_class": self.seat_class,
            "adults": self.adults,
            "price": self.price,
            "currency": self.currency,
            "airline": self.airline,
            "price_level": self.price_level,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceRecord":
        """Create from dictionary."""
        recorded_at = data.get("recorded_at")
        if isinstance(recorded_at, str):
            recorded_at = datetime.fromisoformat(recorded_at)
        return cls(
            id=data.get("id"),
            origin=data.get("origin", ""),
            destination=data.get("destination", ""),
            departure_date=data.get("departure_date", ""),
            return_date=data.get("return_date"),
            trip_type=data.get("trip_type", "one-way"),
            seat_class=data.get("seat_class", "economy"),
            adults=data.get("adults", 1),
            price=data.get("price", 0.0),
            currency=data.get("currency", "USD"),
            airline=data.get("airline"),
            price_level=data.get("price_level"),
            recorded_at=recorded_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class PriceAlert:
    """Configuration for a price alert."""
    id: Optional[int] = None
    origin: str = ""
    destination: str = ""
    departure_date: str = ""
    return_date: Optional[str] = None
    trip_type: str = "one-way"
    seat_class: str = "economy"
    adults: int = 1
    target_price: float = 0.0  # Alert when price <= this
    currency: str = "USD"
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "trip_type": self.trip_type,
            "seat_class": self.seat_class,
            "adults": self.adults,
            "target_price": self.target_price,
            "currency": self.currency,
            "webhook_url": self.webhook_url,
            "email": self.email,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PriceAlert":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        triggered_at = data.get("triggered_at")
        if isinstance(triggered_at, str):
            triggered_at = datetime.fromisoformat(triggered_at)
        return cls(
            id=data.get("id"),
            origin=data.get("origin", ""),
            destination=data.get("destination", ""),
            departure_date=data.get("departure_date", ""),
            return_date=data.get("return_date"),
            trip_type=data.get("trip_type", "one-way"),
            seat_class=data.get("seat_class", "economy"),
            adults=data.get("adults", 1),
            target_price=data.get("target_price", 0.0),
            currency=data.get("currency", "USD"),
            webhook_url=data.get("webhook_url"),
            email=data.get("email"),
            is_active=data.get("is_active", True),
            created_at=created_at,
            triggered_at=triggered_at,
            metadata=data.get("metadata", {}),
        )


@dataclass 
class TrackedRoute:
    """A route being tracked for price changes."""
    id: Optional[int] = None
    origin: str = ""
    destination: str = ""
    departure_date: str = ""
    return_date: Optional[str] = None
    trip_type: str = "one-way"
    seat_class: str = "economy"
    adults: int = 1
    check_interval_minutes: int = 60  # How often to check
    is_active: bool = True
    last_checked: Optional[datetime] = None
    last_price: Optional[float] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "trip_type": self.trip_type,
            "seat_class": self.seat_class,
            "adults": self.adults,
            "check_interval_minutes": self.check_interval_minutes,
            "is_active": self.is_active,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_price": self.last_price,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrackedRoute":
        """Create from dictionary."""
        last_checked = data.get("last_checked")
        if isinstance(last_checked, str):
            last_checked = datetime.fromisoformat(last_checked)
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            id=data.get("id"),
            origin=data.get("origin", ""),
            destination=data.get("destination", ""),
            departure_date=data.get("departure_date", ""),
            return_date=data.get("return_date"),
            trip_type=data.get("trip_type", "one-way"),
            seat_class=data.get("seat_class", "economy"),
            adults=data.get("adults", 1),
            check_interval_minutes=data.get("check_interval_minutes", 60),
            is_active=data.get("is_active", True),
            last_checked=last_checked,
            last_price=data.get("last_price"),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# Storage Backend Abstract Base
# ============================================================================

class PriceStorageBackend(ABC):
    """Abstract base class for price storage backends."""
    
    @abstractmethod
    def save_price(self, record: PriceRecord) -> int:
        """Save a price record. Returns the record ID."""
        pass
    
    @abstractmethod
    def get_price_history(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[PriceRecord]:
        """Get price history for a route."""
        pass
    
    @abstractmethod
    def get_latest_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
    ) -> Optional[PriceRecord]:
        """Get the most recent price for a route."""
        pass
    
    @abstractmethod
    def save_alert(self, alert: PriceAlert) -> int:
        """Save a price alert. Returns the alert ID."""
        pass
    
    @abstractmethod
    def get_alerts(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get price alerts."""
        pass
    
    @abstractmethod
    def update_alert(self, alert_id: int, **kwargs) -> bool:
        """Update an alert. Returns True if successful."""
        pass
    
    @abstractmethod
    def delete_alert(self, alert_id: int) -> bool:
        """Delete an alert. Returns True if successful."""
        pass
    
    @abstractmethod
    def save_tracked_route(self, route: TrackedRoute) -> int:
        """Save a tracked route. Returns the route ID."""
        pass
    
    @abstractmethod
    def get_tracked_routes(self, active_only: bool = True) -> List[TrackedRoute]:
        """Get all tracked routes."""
        pass
    
    @abstractmethod
    def update_tracked_route(self, route_id: int, **kwargs) -> bool:
        """Update a tracked route. Returns True if successful."""
        pass
    
    @abstractmethod
    def delete_tracked_route(self, route_id: int) -> bool:
        """Delete a tracked route. Returns True if successful."""
        pass
    
    @abstractmethod
    def get_routes_due_for_check(self) -> List[TrackedRoute]:
        """Get routes that are due for a price check."""
        pass


# ============================================================================
# SQLite Backend
# ============================================================================

class SQLitePriceStorage(PriceStorageBackend):
    """SQLite-based price storage backend."""
    
    def __init__(self, db_path: Union[str, Path] = "flight_prices.db"):
        """
        Initialize SQLite storage.
        
        Args:
            db_path: Path to the SQLite database file.
                     Use ":memory:" for in-memory database.
        """
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def _cursor(self):
        """Context manager for database cursor with auto-commit."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def _init_database(self):
        """Initialize database tables."""
        with self._cursor() as cursor:
            # Price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    trip_type TEXT DEFAULT 'one-way',
                    seat_class TEXT DEFAULT 'economy',
                    adults INTEGER DEFAULT 1,
                    price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    airline TEXT,
                    price_level TEXT,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_route 
                ON price_history(origin, destination, departure_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_recorded 
                ON price_history(recorded_at)
            """)
            
            # Price alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    trip_type TEXT DEFAULT 'one-way',
                    seat_class TEXT DEFAULT 'economy',
                    adults INTEGER DEFAULT 1,
                    target_price REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    webhook_url TEXT,
                    email TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    triggered_at TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_route 
                ON price_alerts(origin, destination, departure_date)
            """)
            
            # Tracked routes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracked_routes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT,
                    trip_type TEXT DEFAULT 'one-way',
                    seat_class TEXT DEFAULT 'economy',
                    adults INTEGER DEFAULT 1,
                    check_interval_minutes INTEGER DEFAULT 60,
                    is_active INTEGER DEFAULT 1,
                    last_checked TIMESTAMP,
                    last_price REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracked_active 
                ON tracked_routes(is_active, last_checked)
            """)
    
    def save_price(self, record: PriceRecord) -> int:
        """Save a price record."""
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO price_history (
                    origin, destination, departure_date, return_date,
                    trip_type, seat_class, adults, price, currency,
                    airline, price_level, recorded_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.origin,
                record.destination,
                record.departure_date,
                record.return_date,
                record.trip_type,
                record.seat_class,
                record.adults,
                record.price,
                record.currency,
                record.airline,
                record.price_level,
                record.recorded_at or datetime.now(),
                json.dumps(record.metadata),
            ))
            return cursor.lastrowid or 0
    
    def get_price_history(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> List[PriceRecord]:
        """Get price history for a route."""
        with self._cursor() as cursor:
            query = """
                SELECT * FROM price_history
                WHERE origin = ? AND destination = ?
                AND recorded_at >= datetime('now', ?)
            """
            params: List[Any] = [origin, destination, f"-{days} days"]
            
            if departure_date:
                query += " AND departure_date = ?"
                params.append(departure_date)
            
            query += " ORDER BY recorded_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_price_record(row) for row in rows]
    
    def get_latest_price(
        self,
        origin: str,
        destination: str,
        departure_date: str,
    ) -> Optional[PriceRecord]:
        """Get the most recent price for a route."""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT * FROM price_history
                WHERE origin = ? AND destination = ? AND departure_date = ?
                ORDER BY recorded_at DESC LIMIT 1
            """, (origin, destination, departure_date))
            row = cursor.fetchone()
            return self._row_to_price_record(row) if row else None
    
    def _row_to_price_record(self, row: sqlite3.Row) -> PriceRecord:
        """Convert a database row to a PriceRecord."""
        recorded_at = row["recorded_at"]
        if isinstance(recorded_at, str):
            recorded_at = datetime.fromisoformat(recorded_at)
        
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return PriceRecord(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            departure_date=row["departure_date"],
            return_date=row["return_date"],
            trip_type=row["trip_type"],
            seat_class=row["seat_class"],
            adults=row["adults"],
            price=row["price"],
            currency=row["currency"],
            airline=row["airline"],
            price_level=row["price_level"],
            recorded_at=recorded_at,
            metadata=metadata or {},
        )
    
    def save_alert(self, alert: PriceAlert) -> int:
        """Save a price alert."""
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO price_alerts (
                    origin, destination, departure_date, return_date,
                    trip_type, seat_class, adults, target_price, currency,
                    webhook_url, email, is_active, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.origin,
                alert.destination,
                alert.departure_date,
                alert.return_date,
                alert.trip_type,
                alert.seat_class,
                alert.adults,
                alert.target_price,
                alert.currency,
                alert.webhook_url,
                alert.email,
                1 if alert.is_active else 0,
                alert.created_at or datetime.now(),
                json.dumps(alert.metadata),
            ))
            return cursor.lastrowid or 0
    
    def get_alerts(
        self,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        active_only: bool = True,
    ) -> List[PriceAlert]:
        """Get price alerts."""
        with self._cursor() as cursor:
            query = "SELECT * FROM price_alerts WHERE 1=1"
            params: List[Any] = []
            
            if origin:
                query += " AND origin = ?"
                params.append(origin)
            if destination:
                query += " AND destination = ?"
                params.append(destination)
            if active_only:
                query += " AND is_active = 1"
            
            query += " ORDER BY created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [self._row_to_alert(row) for row in rows]
    
    def _row_to_alert(self, row: sqlite3.Row) -> PriceAlert:
        """Convert a database row to a PriceAlert."""
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        triggered_at = row["triggered_at"]
        if isinstance(triggered_at, str):
            triggered_at = datetime.fromisoformat(triggered_at)
        
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return PriceAlert(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            departure_date=row["departure_date"],
            return_date=row["return_date"],
            trip_type=row["trip_type"],
            seat_class=row["seat_class"],
            adults=row["adults"],
            target_price=row["target_price"],
            currency=row["currency"],
            webhook_url=row["webhook_url"],
            email=row["email"],
            is_active=bool(row["is_active"]),
            created_at=created_at,
            triggered_at=triggered_at,
            metadata=metadata or {},
        )
    
    def update_alert(self, alert_id: int, **kwargs) -> bool:
        """Update an alert."""
        if not kwargs:
            return False
        
        # Handle special fields
        if "is_active" in kwargs:
            kwargs["is_active"] = 1 if kwargs["is_active"] else 0
        if "metadata" in kwargs:
            kwargs["metadata"] = json.dumps(kwargs["metadata"])
        if "triggered_at" in kwargs and isinstance(kwargs["triggered_at"], datetime):
            kwargs["triggered_at"] = kwargs["triggered_at"].isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [alert_id]
        
        with self._cursor() as cursor:
            cursor.execute(
                f"UPDATE price_alerts SET {set_clause} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0
    
    def delete_alert(self, alert_id: int) -> bool:
        """Delete an alert."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
            return cursor.rowcount > 0
    
    def save_tracked_route(self, route: TrackedRoute) -> int:
        """Save a tracked route."""
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO tracked_routes (
                    origin, destination, departure_date, return_date,
                    trip_type, seat_class, adults, check_interval_minutes,
                    is_active, last_checked, last_price, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                route.origin,
                route.destination,
                route.departure_date,
                route.return_date,
                route.trip_type,
                route.seat_class,
                route.adults,
                route.check_interval_minutes,
                1 if route.is_active else 0,
                route.last_checked,
                route.last_price,
                route.created_at or datetime.now(),
                json.dumps(route.metadata),
            ))
            return cursor.lastrowid or 0
    
    def get_tracked_routes(self, active_only: bool = True) -> List[TrackedRoute]:
        """Get all tracked routes."""
        with self._cursor() as cursor:
            query = "SELECT * FROM tracked_routes"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            return [self._row_to_tracked_route(row) for row in rows]
    
    def _row_to_tracked_route(self, row: sqlite3.Row) -> TrackedRoute:
        """Convert a database row to a TrackedRoute."""
        last_checked = row["last_checked"]
        if isinstance(last_checked, str):
            last_checked = datetime.fromisoformat(last_checked)
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return TrackedRoute(
            id=row["id"],
            origin=row["origin"],
            destination=row["destination"],
            departure_date=row["departure_date"],
            return_date=row["return_date"],
            trip_type=row["trip_type"],
            seat_class=row["seat_class"],
            adults=row["adults"],
            check_interval_minutes=row["check_interval_minutes"],
            is_active=bool(row["is_active"]),
            last_checked=last_checked,
            last_price=row["last_price"],
            created_at=created_at,
            metadata=metadata or {},
        )
    
    def update_tracked_route(self, route_id: int, **kwargs) -> bool:
        """Update a tracked route."""
        if not kwargs:
            return False
        
        # Handle special fields
        if "is_active" in kwargs:
            kwargs["is_active"] = 1 if kwargs["is_active"] else 0
        if "metadata" in kwargs:
            kwargs["metadata"] = json.dumps(kwargs["metadata"])
        if "last_checked" in kwargs and isinstance(kwargs["last_checked"], datetime):
            kwargs["last_checked"] = kwargs["last_checked"].isoformat()
        
        set_clause = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values()) + [route_id]
        
        with self._cursor() as cursor:
            cursor.execute(
                f"UPDATE tracked_routes SET {set_clause} WHERE id = ?",
                values,
            )
            return cursor.rowcount > 0
    
    def delete_tracked_route(self, route_id: int) -> bool:
        """Delete a tracked route."""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM tracked_routes WHERE id = ?", (route_id,))
            return cursor.rowcount > 0
    
    def get_routes_due_for_check(self) -> List[TrackedRoute]:
        """Get routes that are due for a price check."""
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT * FROM tracked_routes
                WHERE is_active = 1
                AND (
                    last_checked IS NULL
                    OR datetime(last_checked, '+' || check_interval_minutes || ' minutes') <= datetime('now')
                )
                ORDER BY last_checked ASC NULLS FIRST
            """)
            rows = cursor.fetchall()
            return [self._row_to_tracked_route(row) for row in rows]
    
    def get_price_stats(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get price statistics for a route."""
        with self._cursor() as cursor:
            query = """
                SELECT 
                    MIN(price) as min_price,
                    MAX(price) as max_price,
                    AVG(price) as avg_price,
                    COUNT(*) as record_count
                FROM price_history
                WHERE origin = ? AND destination = ?
                AND recorded_at >= datetime('now', ?)
            """
            params: List[Any] = [origin, destination, f"-{days} days"]
            
            if departure_date:
                query += " AND departure_date = ?"
                params.append(departure_date)
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if row and row["record_count"] > 0:
                return {
                    "min_price": row["min_price"],
                    "max_price": row["max_price"],
                    "avg_price": round(row["avg_price"], 2),
                    "record_count": row["record_count"],
                    "days_analyzed": days,
                }
            return {
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "record_count": 0,
                "days_analyzed": days,
            }
    
    def close(self):
        """Close the database connection."""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


# ============================================================================
# Global Storage Instance
# ============================================================================

_storage: Optional[PriceStorageBackend] = None
_storage_lock = threading.Lock()


def get_price_storage(
    backend: Literal["sqlite"] = "sqlite",
    **kwargs,
) -> PriceStorageBackend:
    """
    Get the global price storage instance.
    
    Args:
        backend: Storage backend type ("sqlite" for now)
        **kwargs: Backend-specific configuration
        
    Returns:
        PriceStorageBackend instance
    """
    global _storage
    
    with _storage_lock:
        if _storage is None:
            if backend == "sqlite":
                db_path = kwargs.get("db_path", "flight_prices.db")
                _storage = SQLitePriceStorage(db_path)
            else:
                raise ValueError(f"Unknown backend: {backend}")
        return _storage


def reset_price_storage():
    """Reset the global storage instance (for testing)."""
    global _storage
    with _storage_lock:
        if _storage is not None:
            if hasattr(_storage, "close"):
                _storage.close()
            _storage = None
