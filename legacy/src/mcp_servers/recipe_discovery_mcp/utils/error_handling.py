"""Comprehensive error handling framework for Recipe Discovery MCP"""

import asyncio
import traceback
from functools import wraps
from typing import Callable, Any, Dict, Optional, Union
from datetime import datetime
import structlog

from ..models import RecipeData


logger = structlog.get_logger()


class MCPError(Exception):
    """Base exception for MCP server errors"""
    def __init__(self, message: str, error_code: str = "MCP_ERROR", details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = datetime.now()
        super().__init__(message)


class ScrapingError(MCPError):
    """Errors related to recipe scraping operations"""
    def __init__(self, url: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.url = url
        super().__init__(message, "SCRAPING_ERROR", details)


class NetworkError(MCPError):
    """Network-related errors (timeouts, connection failures)"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "NETWORK_ERROR", details)


class RateLimitError(MCPError):
    """Rate limiting errors"""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, "RATE_LIMIT_ERROR", details)


class ConfigurationError(MCPError):
    """Configuration-related errors"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFIG_ERROR", details)


class ValidationError(MCPError):
    """Data validation errors"""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        super().__init__(message, "VALIDATION_ERROR", details)


def handle_scraping_errors(func: Callable) -> Callable:
    """Decorator for comprehensive error handling in scraping operations
    
    Handles network errors, parsing failures, rate limiting, and other
    common scraping issues with appropriate logging and error responses.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = datetime.now()
        function_name = func.__name__
        
        try:
            logger.info(
                "Function started",
                function=function_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            result = await func(*args, **kwargs)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                "Function completed successfully",
                function=function_name,
                duration_seconds=duration
            )
            
            return result
            
        except ScrapingError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Scraping error occurred",
                function=function_name,
                error_code=e.error_code,
                error_message=e.message,
                url=getattr(e, 'url', None),
                details=e.details,
                duration_seconds=duration
            )
            raise
            
        except NetworkError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Network error occurred",
                function=function_name,
                error_code=e.error_code,
                error_message=e.message,
                details=e.details,
                duration_seconds=duration
            )
            raise
            
        except RateLimitError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.warning(
                "Rate limit encountered",
                function=function_name,
                error_message=e.message,
                retry_after=e.details.get("retry_after"),
                duration_seconds=duration
            )
            raise
            
        except asyncio.TimeoutError as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Timeout error occurred",
                function=function_name,
                error_message=str(e),
                duration_seconds=duration
            )
            raise NetworkError(
                f"Operation timed out in {function_name}",
                {"timeout_seconds": duration}
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(
                "Unexpected error occurred",
                function=function_name,
                error_type=type(e).__name__,
                error_message=str(e),
                traceback=traceback.format_exc(),
                duration_seconds=duration
            )
            raise MCPError(
                f"Unexpected error in {function_name}: {str(e)}",
                "UNEXPECTED_ERROR",
                {
                    "original_error": str(e),
                    "error_type": type(e).__name__,
                    "function": function_name
                }
            )
    
    return wrapper


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (NetworkError, RateLimitError)
) -> Any:
    """Retry function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types to retry on
        
    Returns:
        Result of successful function call
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func()
            
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(
                    "All retry attempts failed",
                    attempts=attempt + 1,
                    max_retries=max_retries,
                    final_error=str(e)
                )
                break
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            # Special handling for rate limit errors
            if isinstance(e, RateLimitError) and e.details.get("retry_after"):
                delay = max(delay, e.details["retry_after"])
            
            logger.warning(
                "Retrying after error",
                attempt=attempt + 1,
                max_retries=max_retries,
                delay_seconds=delay,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            await asyncio.sleep(delay)
            
        except Exception as e:
            # Non-retryable exceptions are re-raised immediately
            logger.error(
                "Non-retryable error occurred",
                attempt=attempt + 1,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise
    
    # If we get here, all retries failed
    raise last_exception


def safe_url_extraction(url: str) -> str:
    """Safely extract and validate URL for logging
    
    Removes sensitive query parameters and validates format.
    """
    try:
        from urllib.parse import urlparse, parse_qs
        
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return "invalid_url"
        
        # Remove potentially sensitive query parameters
        sensitive_params = ['api_key', 'token', 'password', 'secret']
        if parsed.query:
            query_params = parse_qs(parsed.query)
            safe_params = {
                k: v for k, v in query_params.items()
                if not any(sensitive in k.lower() for sensitive in sensitive_params)
            }
            if safe_params:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?..."
        
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    except Exception:
        return "url_parse_error"


def create_error_response(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create standardized error response for MCP tools
    
    Args:
        error: Exception that occurred
        context: Additional context information
        
    Returns:
        Standardized error response dictionary
    """
    error_response = {
        "success": False,
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat()
        }
    }
    
    if isinstance(error, MCPError):
        error_response["error"]["code"] = error.error_code
        error_response["error"]["details"] = error.details
    
    if context:
        error_response["context"] = context
    
    return error_response