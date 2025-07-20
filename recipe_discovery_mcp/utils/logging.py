"""Structured logging setup for Recipe Discovery MCP Server"""

import sys
import structlog
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from ..config import get_config


def get_logger(name: str = __name__):
    """Get a structured logger instance
    
    Args:
        name: Logger name, typically __name__
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger().bind(component=name)


def setup_structured_logging() -> None:
    """Configure structured logging for the MCP server
    
    Sets up JSON logging for production and human-readable logs for development.
    Includes request tracing and performance metrics.
    """
    config = get_config()
    
    # Configure structlog processors
    processors = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="ISO", utc=True),
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Filter out sensitive data
        _filter_sensitive_data,
        # Stack info for errors
        structlog.processors.StackInfoRenderer(),
    ]
    
    # Choose output format based on environment
    if config.is_debug():
        # Human-readable format for development
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])
    else:
        # JSON format for production
        processors.extend([
            structlog.processors.JSONRenderer(),
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Configure Python logging
    import logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, config.get_log_level()),
    )


def _filter_sensitive_data(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out sensitive information from logs"""
    sensitive_keys = {
        'password', 'token', 'secret', 'key', 'auth', 'credential',
        'api_key', 'access_token', 'refresh_token'
    }
    
    # Recursively filter sensitive data
    def filter_dict(d: Any) -> Any:
        if isinstance(d, dict):
            filtered = {}
            for k, v in d.items():
                if any(sensitive in k.lower() for sensitive in sensitive_keys):
                    filtered[k] = "[REDACTED]"
                else:
                    filtered[k] = filter_dict(v)
            return filtered
        elif isinstance(d, list):
            return [filter_dict(item) for item in d]
        else:
            return d
    
    return filter_dict(event_dict)


class RequestTracker:
    """Track request lifecycle for logging and metrics"""
    
    def __init__(self, request_id: str, operation: str):
        self.request_id = request_id
        self.operation = operation
        self.start_time = datetime.now()
        self.logger = structlog.get_logger().bind(
            request_id=request_id,
            operation=operation
        )
    
    def log_start(self, **context) -> None:
        """Log request start"""
        self.logger.info("Request started", **context)
    
    def log_progress(self, message: str, **context) -> None:
        """Log request progress"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(message, elapsed_seconds=elapsed, **context)
    
    def log_success(self, **context) -> None:
        """Log successful completion"""
        duration = (datetime.now() - self.start_time).total_seconds()
        self.logger.info(
            "Request completed successfully",
            duration_seconds=duration,
            **context
        )
    
    def log_error(self, error: Exception, **context) -> None:
        """Log request error"""
        duration = (datetime.now() - self.start_time).total_seconds()
        self.logger.error(
            "Request failed",
            error_type=type(error).__name__,
            error_message=str(error),
            duration_seconds=duration,
            **context
        )
    
    def log_warning(self, message: str, **context) -> None:
        """Log request warning"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.warning(message, elapsed_seconds=elapsed, **context)


class PerformanceLogger:
    """Log performance metrics and server statistics"""
    
    def __init__(self):
        self.logger = structlog.get_logger().bind(component="performance")
        self.start_time = datetime.now()
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
    
    def log_request_metrics(
        self,
        duration: float,
        success: bool,
        url: Optional[str] = None,
        **context
    ) -> None:
        """Log individual request metrics"""
        self.request_count += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
        
        self.logger.info(
            "Request metrics",
            duration_seconds=duration,
            success=success,
            url=self._safe_url(url) if url else None,
            total_requests=self.request_count,
            success_rate=self._calculate_success_rate(),
            **context
        )
    
    def log_server_metrics(self, **context) -> None:
        """Log server-wide metrics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        self.logger.info(
            "Server metrics",
            uptime_seconds=uptime,
            total_requests=self.request_count,
            successful_requests=self.success_count,
            failed_requests=self.error_count,
            success_rate=self._calculate_success_rate(),
            requests_per_second=self._calculate_rps(),
            **context
        )
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.request_count == 0:
            return 100.0
        return (self.success_count / self.request_count) * 100
    
    def _calculate_rps(self) -> float:
        """Calculate requests per second"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        if uptime == 0:
            return 0.0
        return self.request_count / uptime
    
    def _safe_url(self, url: str) -> str:
        """Safely log URL without sensitive information"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        except Exception:
            return "invalid_url"


# Global performance logger instance
_performance_logger: Optional[PerformanceLogger] = None


def get_performance_logger() -> PerformanceLogger:
    """Get global performance logger instance"""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger()
    return _performance_logger


def create_request_tracker(request_id: str, operation: str) -> RequestTracker:
    """Create a new request tracker for logging"""
    return RequestTracker(request_id, operation)


def log_server_startup(config: Any) -> None:
    """Log server startup information"""
    logger = structlog.get_logger().bind(component="startup")
    
    logger.info(
        "MCP Server starting up",
        server_name=config.server_name,
        log_level=config.log_level,
        max_concurrent=config.max_concurrent_requests,
        rate_limit=config.requests_per_second,
        debug_mode=config.is_debug()
    )


def log_server_shutdown() -> None:
    """Log server shutdown information"""
    logger = structlog.get_logger().bind(component="shutdown")
    perf_logger = get_performance_logger()
    
    uptime = (datetime.now() - perf_logger.start_time).total_seconds()
    
    logger.info(
        "MCP Server shutting down",
        uptime_seconds=uptime,
        total_requests=perf_logger.request_count,
        final_success_rate=perf_logger._calculate_success_rate()
    )