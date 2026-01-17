"""Retry management system with exponential backoff

Provides intelligent retry logic with exponential backoff, jitter, and
configurable retry strategies for handling transient failures in
recipe scraping operations.
"""

import asyncio
import random
import time
from typing import Callable, Any, Optional, Type, Tuple, List, Union
from functools import wraps
from dataclasses import dataclass
import structlog

from .error_handling import NetworkError, MCPError


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_max: float = 1.0
    
    # Exception types that should trigger retries
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        NetworkError,
        ConnectionError,
        TimeoutError,
        OSError
    )
    
    # Exception types that should NOT trigger retries
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (
        ValueError,
        TypeError,
        KeyError
    )


class RetryManager:
    """Retry manager with exponential backoff and intelligent error handling
    
    Provides flexible retry logic for async operations with configurable
    backoff strategies and exception filtering.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """Initialize retry manager
        
        Args:
            config: Retry configuration. Uses defaults if None.
        """
        self.config = config or RetryConfig()
        self.logger = structlog.get_logger().bind(component="retry_manager")
        
        self.logger.debug(
            "Retry manager initialized",
            max_retries=self.config.max_retries,
            base_delay=self.config.base_delay,
            max_delay=self.config.max_delay
        )
    
    async def with_retry(
        self, 
        func: Callable, 
        *args, 
        operation_name: str = "operation",
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry
        
        Args:
            func: Async function to execute with retry
            *args: Positional arguments for func
            operation_name: Name for logging purposes
            **kwargs: Keyword arguments for func
            
        Returns:
            Result of successful function execution
            
        Raises:
            Last encountered exception after all retries exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                if attempt > 0:
                    self.logger.info(
                        "Retrying operation",
                        operation=operation_name,
                        attempt=attempt,
                        max_retries=self.config.max_retries
                    )
                
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(
                        "Operation succeeded on retry",
                        operation=operation_name,
                        attempt=attempt
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Check if this exception type should trigger a retry
                if not self._should_retry(e, attempt):
                    self.logger.warning(
                        "Operation failed with non-retryable error",
                        operation=operation_name,
                        attempt=attempt,
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                    raise e
                
                # If this is the last attempt, don't wait
                if attempt >= self.config.max_retries:
                    self.logger.error(
                        "Operation failed after all retries",
                        operation=operation_name,
                        total_attempts=attempt + 1,
                        final_error_type=type(e).__name__,
                        final_error_message=str(e)
                    )
                    break
                
                # Calculate delay for next attempt
                delay = self._calculate_delay(attempt)
                
                self.logger.warning(
                    "Operation failed, will retry",
                    operation=operation_name,
                    attempt=attempt,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    retry_delay=delay
                )
                
                # Wait before next attempt
                await asyncio.sleep(delay)
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            raise MCPError(f"Operation {operation_name} failed with unknown error")
    
    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry
        
        Args:
            exception: The exception that occurred
            attempt: Current attempt number (0-based)
            
        Returns:
            True if retry should be attempted
        """
        # No more retries available
        if attempt >= self.config.max_retries:
            return False
        
        # Check for explicitly non-retryable exceptions
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # Check for explicitly retryable exceptions
        if isinstance(exception, self.config.retryable_exceptions):
            return True
        
        # Check for common HTTP/network error patterns in exception message
        error_message = str(exception).lower()
        retryable_patterns = [
            "timeout",
            "connection",
            "503",  # Service Unavailable
            "502",  # Bad Gateway
            "504",  # Gateway Timeout
            "429",  # Too Many Requests
            "rate limit",
            "temporarily unavailable"
        ]
        
        for pattern in retryable_patterns:
            if pattern in error_message:
                return True
        
        # Default to no retry for unknown exceptions
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the next retry attempt
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            jitter_amount = random.uniform(0, self.config.jitter_max)
            delay += jitter_amount
        
        return delay
    
    def get_retry_delays(self) -> List[float]:
        """Get the sequence of delays that would be used for retries
        
        Returns:
            List of delay times for each retry attempt
        """
        delays = []
        for attempt in range(self.config.max_retries):
            delay = self._calculate_delay(attempt)
            delays.append(delay)
        return delays


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    operation_name: Optional[str] = None
):
    """Decorator for automatic retry with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        operation_name: Name for logging (uses function name if None)
        
    Returns:
        Decorated function with retry capability
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay
            )
            retry_manager = RetryManager(config)
            
            name = operation_name or func.__name__
            return await retry_manager.with_retry(func, *args, operation_name=name, **kwargs)
        
        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for failing fast when service is down
    
    Prevents continuous retries against a failing service by tracking
    failure rates and temporarily blocking requests when failure threshold
    is exceeded.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time to wait before attempting recovery
            expected_exception: Exception type that counts as failure
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # Circuit state
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
        self.logger = structlog.get_logger().bind(component="circuit_breaker")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Function result
            
        Raises:
            MCPError: If circuit is open
            Original exception: If function fails
        """
        # Check circuit state
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                self.logger.info("Circuit breaker attempting recovery")
            else:
                raise MCPError(
                    f"Circuit breaker is open. Service unavailable. "
                    f"Will retry after {self.recovery_timeout} seconds."
                )
        
        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset failure count
            self._on_success()
            return result
            
        except self.expected_exception as e:
            # Handle expected failures
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful execution"""
        if self.state == "half-open":
            self.logger.info("Circuit breaker recovery successful")
        
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self) -> None:
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(
                "Circuit breaker opened due to failures",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state
        
        Returns:
            Dictionary with current state information
        """
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
            "time_until_retry": (
                max(0, self.recovery_timeout - (time.time() - self.last_failure_time))
                if self.last_failure_time else 0
            )
        }
    
    def reset(self) -> None:
        """Manually reset circuit breaker"""
        self.logger.info("Manually resetting circuit breaker")
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"