"""
Structured error handling for AI agent integration.

This module provides error types with standardized codes, messages,
and recovery suggestions that AI agents can easily parse and act upon.
"""

from enum import Enum
from typing import Optional, Any

# Try to import Pydantic for validation
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback to dataclass-like behavior
    from dataclasses import dataclass
    BaseModel = object  # type: ignore
    def Field(*args, **kwargs):  # type: ignore
        return kwargs.get('default', None)


class ErrorCode(str, Enum):
    """
    Standardized error codes for AI agent consumption.
    
    These codes allow agents to programmatically handle different
    error types without parsing error messages.
    """
    
    # Input validation errors
    INVALID_AIRPORT = "INVALID_AIRPORT"
    INVALID_DATE = "INVALID_DATE"
    INVALID_PASSENGERS = "INVALID_PASSENGERS"
    INVALID_REQUEST = "INVALID_REQUEST"
    
    # Search result errors  
    NO_FLIGHTS_FOUND = "NO_FLIGHTS_FOUND"
    ROUTE_NOT_AVAILABLE = "ROUTE_NOT_AVAILABLE"
    
    # Network/API errors
    RATE_LIMITED = "RATE_LIMITED"
    BLOCKED = "BLOCKED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    
    # Parsing errors
    PARSE_ERROR = "PARSE_ERROR"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    
    # System errors
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


if PYDANTIC_AVAILABLE:
    class FlightSearchError(BaseModel):
        """
        Structured error response for AI agents.
        
        Provides machine-readable error information with human-friendly
        descriptions and actionable recovery suggestions.
        """
        
        code: ErrorCode = Field(
            description="Machine-readable error code"
        )
        message: str = Field(
            description="Human-readable error message"
        )
        details: Optional[dict] = Field(
            default=None,
            description="Additional error context (e.g., invalid field names)"
        )
        recoverable: bool = Field(
            default=True,
            description="Whether the error can be recovered from with different input"
        )
        suggested_action: Optional[str] = Field(
            default=None,
            description="Suggested action to resolve the error"
        )
        retry_after_seconds: Optional[int] = Field(
            default=None,
            description="Seconds to wait before retrying (for rate limit errors)"
        )
        
        @classmethod
        def from_exception(cls, e: Exception) -> "FlightSearchError":
            """
            Convert an exception to a structured FlightSearchError.
            
            Analyzes the exception message to determine the appropriate
            error code and provide helpful recovery suggestions.
            
            Args:
                e: The exception to convert
                
            Returns:
                FlightSearchError with appropriate code and message
            """
            error_str = str(e).lower()
            
            # No flights found
            if "no flights found" in error_str or "no results" in error_str:
                return cls(
                    code=ErrorCode.NO_FLIGHTS_FOUND,
                    message="No flights found for the specified route and dates",
                    recoverable=True,
                    suggested_action="Try different dates, nearby airports, or fewer stops restriction"
                )
            
            # Rate limiting
            if "429" in error_str or "rate" in error_str or "too many" in error_str:
                return cls(
                    code=ErrorCode.RATE_LIMITED,
                    message="Rate limited by Google Flights",
                    recoverable=True,
                    suggested_action="Wait 30-60 seconds before retrying",
                    retry_after_seconds=60
                )
            
            # Blocked/forbidden
            if "403" in error_str or "blocked" in error_str or "forbidden" in error_str:
                return cls(
                    code=ErrorCode.BLOCKED,
                    message="Request blocked by Google Flights",
                    recoverable=True,
                    suggested_action="Use 'fallback' or 'bright-data' fetch mode"
                )
            
            # Network errors
            if any(x in error_str for x in ["connection", "network", "dns", "socket"]):
                return cls(
                    code=ErrorCode.NETWORK_ERROR,
                    message="Network connection error",
                    recoverable=True,
                    suggested_action="Check internet connection and retry"
                )
            
            # Timeout
            if "timeout" in error_str or "timed out" in error_str:
                return cls(
                    code=ErrorCode.TIMEOUT,
                    message="Request timed out",
                    recoverable=True,
                    suggested_action="Retry the request or use 'fallback' mode"
                )
            
            # Invalid airport
            if "airport" in error_str or "iata" in error_str:
                return cls(
                    code=ErrorCode.INVALID_AIRPORT,
                    message="Invalid airport code provided",
                    recoverable=True,
                    suggested_action="Verify airport codes using search_airports() function",
                    details={"original_error": str(e)}
                )
            
            # Invalid date
            if "date" in error_str:
                return cls(
                    code=ErrorCode.INVALID_DATE,
                    message="Invalid date format or value",
                    recoverable=True,
                    suggested_action="Use YYYY-MM-DD format with a future date"
                )
            
            # Passenger errors
            if "passenger" in error_str or "infant" in error_str or "adult" in error_str:
                return cls(
                    code=ErrorCode.INVALID_PASSENGERS,
                    message="Invalid passenger configuration",
                    recoverable=True,
                    suggested_action="Ensure total passengers ≤9 and lap infants ≤ adults"
                )
            
            # Parse errors
            if "parse" in error_str or "malformed" in error_str or "json" in error_str:
                return cls(
                    code=ErrorCode.PARSE_ERROR,
                    message="Failed to parse flight data from response",
                    recoverable=True,
                    suggested_action="Try 'fallback' mode or different data_source"
                )
            
            # HTTP status code errors
            if "status" in error_str:
                import re
                status_match = re.search(r'(\d{3})', str(e))
                status_code = status_match.group(1) if status_match else "unknown"
                return cls(
                    code=ErrorCode.NETWORK_ERROR,
                    message=f"HTTP error {status_code}",
                    recoverable=True,
                    suggested_action="Retry the request with 'fallback' mode",
                    details={"status_code": status_code}
                )
            
            # Unknown error (fallback)
            return cls(
                code=ErrorCode.UNKNOWN_ERROR,
                message=str(e),
                recoverable=False,
                suggested_action="Check input parameters and try again",
                details={"exception_type": type(e).__name__}
            )
        
        def to_dict(self) -> dict:
            """Convert to dictionary for JSON serialization."""
            return {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "recoverable": self.recoverable,
                "suggested_action": self.suggested_action,
                "retry_after_seconds": self.retry_after_seconds
            }

else:
    # Fallback when Pydantic is not available
    from dataclasses import dataclass
    
    @dataclass
    class FlightSearchError:
        """Structured error response (dataclass fallback)."""
        code: ErrorCode
        message: str
        details: Optional[dict] = None
        recoverable: bool = True
        suggested_action: Optional[str] = None
        retry_after_seconds: Optional[int] = None
        
        @classmethod
        def from_exception(cls, e: Exception) -> "FlightSearchError":
            """Convert an exception to a structured FlightSearchError."""
            error_str = str(e).lower()
            
            if "no flights found" in error_str:
                return cls(
                    code=ErrorCode.NO_FLIGHTS_FOUND,
                    message="No flights found for the specified route and dates",
                    suggested_action="Try different dates or nearby airports"
                )
            
            return cls(
                code=ErrorCode.UNKNOWN_ERROR,
                message=str(e),
                recoverable=False
            )
        
        def to_dict(self) -> dict:
            """Convert to dictionary for JSON serialization."""
            return {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "recoverable": self.recoverable,
                "suggested_action": self.suggested_action,
                "retry_after_seconds": self.retry_after_seconds
            }


class FlightAPIException(Exception):
    """
    Exception with structured error information.
    
    Wraps a FlightSearchError for cases where an exception must be raised
    but structured error information is still needed.
    
    Attributes:
        error: The FlightSearchError with structured information
        
    Example:
        try:
            # ... some operation
        except FlightAPIException as e:
            print(f"Error code: {e.error.code}")
            print(f"Suggestion: {e.error.suggested_action}")
    """
    
    def __init__(self, error: FlightSearchError):
        self.error = error
        super().__init__(error.message)
    
    def to_dict(self) -> dict:
        """Get the error as a dictionary."""
        return self.error.to_dict()
    
    @classmethod
    def from_code(
        cls,
        code: ErrorCode,
        message: Optional[str] = None,
        **kwargs: Any
    ) -> "FlightAPIException":
        """
        Create an exception from an error code.
        
        Args:
            code: The error code
            message: Optional custom message (defaults based on code)
            **kwargs: Additional FlightSearchError fields
            
        Returns:
            FlightAPIException with structured error
        """
        default_messages = {
            ErrorCode.INVALID_AIRPORT: "Invalid airport code provided",
            ErrorCode.INVALID_DATE: "Invalid date format or value",
            ErrorCode.INVALID_PASSENGERS: "Invalid passenger configuration",
            ErrorCode.NO_FLIGHTS_FOUND: "No flights found",
            ErrorCode.RATE_LIMITED: "Rate limited - please wait before retrying",
            ErrorCode.BLOCKED: "Request blocked by server",
            ErrorCode.NETWORK_ERROR: "Network connection error",
            ErrorCode.PARSE_ERROR: "Failed to parse response",
            ErrorCode.UNKNOWN_ERROR: "An unknown error occurred",
        }
        
        error = FlightSearchError(
            code=code,
            message=message or default_messages.get(code, str(code)),
            **kwargs
        )
        return cls(error)


# Convenience functions for creating common errors
def invalid_airport_error(
    airport_code: str,
    field: str = "airport"
) -> FlightSearchError:
    """Create an error for invalid airport codes."""
    return FlightSearchError(
        code=ErrorCode.INVALID_AIRPORT,
        message=f"Invalid airport code: {airport_code}",
        details={"field": field, "value": airport_code},
        recoverable=True,
        suggested_action="Use search_airports() to find valid airport codes"
    )


def invalid_date_error(
    date_str: str,
    reason: str = "Invalid format"
) -> FlightSearchError:
    """Create an error for invalid dates."""
    return FlightSearchError(
        code=ErrorCode.INVALID_DATE,
        message=f"Invalid date '{date_str}': {reason}",
        details={"value": date_str, "reason": reason},
        recoverable=True,
        suggested_action="Use YYYY-MM-DD format with a date in the future"
    )


def no_flights_error(
    origin: str,
    destination: str,
    date: str
) -> FlightSearchError:
    """Create an error when no flights are found."""
    return FlightSearchError(
        code=ErrorCode.NO_FLIGHTS_FOUND,
        message=f"No flights found from {origin} to {destination} on {date}",
        details={"origin": origin, "destination": destination, "date": date},
        recoverable=True,
        suggested_action="Try different dates, nearby airports, or remove max_stops filter"
    )


__all__ = [
    "ErrorCode",
    "FlightSearchError",
    "FlightAPIException",
    # Convenience functions
    "invalid_airport_error",
    "invalid_date_error",
    "no_flights_error",
]
