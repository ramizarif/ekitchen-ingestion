"""Rate limiting system for respectful web scraping

Implements domain-based rate limiting to ensure respectful scraping practices
and avoid overwhelming target websites with requests.
"""

import asyncio
import time
from typing import Dict, Optional
from collections import defaultdict
import structlog

from .config import get_config


class RateLimiter:
    """Rate limiter with per-domain tracking and configurable limits
    
    Ensures respectful scraping by limiting requests per domain based on
    configurable rates. Tracks last request time per domain and enforces
    minimum intervals between requests.
    """
    
    def __init__(self, requests_per_second: Optional[float] = None):
        """Initialize rate limiter
        
        Args:
            requests_per_second: Maximum requests per second per domain
                                If None, uses configuration default
        """
        self.config = get_config()
        self.requests_per_second = requests_per_second or self.config.requests_per_second
        
        # Track last request time per domain
        self.last_request_time: Dict[str, float] = defaultdict(float)
        
        # Track request counts for monitoring
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.blocked_requests: Dict[str, int] = defaultdict(int)
        
        # Calculate minimum interval between requests
        self.min_interval = 1.0 / self.requests_per_second
        
        self.logger = structlog.get_logger().bind(component="rate_limiter")
        self.logger.info(
            "Rate limiter initialized",
            requests_per_second=self.requests_per_second,
            min_interval_seconds=self.min_interval
        )
    
    async def acquire(self, domain: str) -> None:
        """Acquire permission to make request to domain
        
        Blocks until it's safe to make a request to the specified domain
        based on the configured rate limit.
        
        Args:
            domain: Domain name (e.g., "www.example.com")
        """
        if not domain:
            # Skip rate limiting for empty domains
            return
        
        current_time = time.time()
        last_request = self.last_request_time[domain]
        time_since_last = current_time - last_request
        
        # Check if we need to wait
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            
            self.logger.debug(
                "Rate limiting request",
                domain=domain,
                sleep_time=sleep_time,
                time_since_last=time_since_last,
                min_interval=self.min_interval
            )
            
            # Track blocked request
            self.blocked_requests[domain] += 1
            
            # Wait for the required interval
            await asyncio.sleep(sleep_time)
        
        # Update last request time
        self.last_request_time[domain] = time.time()
        self.request_counts[domain] += 1
        
        self.logger.debug(
            "Request permitted",
            domain=domain,
            total_requests=self.request_counts[domain],
            blocked_count=self.blocked_requests[domain]
        )
    
    def get_domain_stats(self, domain: str) -> Dict[str, any]:
        """Get statistics for a specific domain
        
        Args:
            domain: Domain to get stats for
            
        Returns:
            Dictionary with domain-specific statistics
        """
        current_time = time.time()
        last_request = self.last_request_time[domain]
        time_since_last = current_time - last_request if last_request else None
        
        return {
            "domain": domain,
            "total_requests": self.request_counts[domain],
            "blocked_requests": self.blocked_requests[domain],
            "last_request_time": last_request,
            "seconds_since_last_request": time_since_last,
            "can_request_now": (
                time_since_last is None or time_since_last >= self.min_interval
            )
        }
    
    def get_stats(self) -> Dict[str, any]:
        """Get comprehensive rate limiter statistics
        
        Returns:
            Dictionary with rate limiter performance statistics
        """
        total_requests = sum(self.request_counts.values())
        total_blocked = sum(self.blocked_requests.values())
        
        # Calculate per-domain stats
        domain_stats = []
        for domain in set(self.request_counts.keys()) | set(self.blocked_requests.keys()):
            domain_stats.append(self.get_domain_stats(domain))
        
        return {
            "rate_limit_config": {
                "requests_per_second": self.requests_per_second,
                "min_interval_seconds": self.min_interval
            },
            "global_stats": {
                "total_requests": total_requests,
                "total_blocked": total_blocked,
                "blocking_rate": (
                    (total_blocked / total_requests * 100)
                    if total_requests > 0 else 0.0
                ),
                "tracked_domains": len(self.last_request_time)
            },
            "domain_stats": domain_stats
        }
    
    def reset_domain(self, domain: str) -> None:
        """Reset rate limiting state for a specific domain
        
        Useful for testing or when domain policies change.
        
        Args:
            domain: Domain to reset
        """
        self.logger.info("Resetting rate limiter for domain", domain=domain)
        
        if domain in self.last_request_time:
            del self.last_request_time[domain]
        if domain in self.request_counts:
            del self.request_counts[domain]
        if domain in self.blocked_requests:
            del self.blocked_requests[domain]
    
    def reset_all(self) -> None:
        """Reset all rate limiting state
        
        Clears all tracking data and starts fresh.
        """
        self.logger.info("Resetting all rate limiter state")
        
        self.last_request_time.clear()
        self.request_counts.clear()
        self.blocked_requests.clear()
    
    def update_rate(self, requests_per_second: float) -> None:
        """Update the rate limit configuration
        
        Args:
            requests_per_second: New rate limit
        """
        old_rate = self.requests_per_second
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        
        self.logger.info(
            "Rate limit updated",
            old_rate=old_rate,
            new_rate=requests_per_second,
            new_min_interval=self.min_interval
        )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # No cleanup needed for rate limiter
        pass


class AdaptiveRateLimiter(RateLimiter):
    """Advanced rate limiter with adaptive behavior
    
    Extends basic rate limiter with adaptive behavior based on response
    patterns and error rates. Can automatically adjust rates for
    problematic domains.
    """
    
    def __init__(
        self, 
        requests_per_second: Optional[float] = None,
        adaptive_threshold: float = 0.1,  # 10% error rate triggers adaptation
        backoff_multiplier: float = 2.0
    ):
        """Initialize adaptive rate limiter
        
        Args:
            requests_per_second: Base rate limit
            adaptive_threshold: Error rate that triggers adaptation (0.0-1.0)
            backoff_multiplier: How much to reduce rate when adapting
        """
        super().__init__(requests_per_second)
        
        self.adaptive_threshold = adaptive_threshold
        self.backoff_multiplier = backoff_multiplier
        
        # Track errors per domain for adaptive behavior
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.domain_rates: Dict[str, float] = defaultdict(lambda: self.requests_per_second)
        
        self.logger.info(
            "Adaptive rate limiter initialized",
            adaptive_threshold=adaptive_threshold,
            backoff_multiplier=backoff_multiplier
        )
    
    async def acquire(self, domain: str) -> None:
        """Acquire with domain-specific rate limits"""
        if not domain:
            return
        
        # Use domain-specific rate if available
        domain_rate = self.domain_rates[domain]
        original_rate = self.requests_per_second
        
        # Temporarily adjust rate for this domain
        self.requests_per_second = domain_rate
        self.min_interval = 1.0 / domain_rate
        
        try:
            await super().acquire(domain)
        finally:
            # Restore original rate
            self.requests_per_second = original_rate
            self.min_interval = 1.0 / original_rate
    
    def report_error(self, domain: str) -> None:
        """Report an error for adaptive rate adjustment
        
        Args:
            domain: Domain that returned an error
        """
        self.error_counts[domain] += 1
        total_requests = self.request_counts[domain]
        
        if total_requests > 10:  # Need minimum sample size
            error_rate = self.error_counts[domain] / total_requests
            
            if error_rate > self.adaptive_threshold:
                # Reduce rate for this domain
                old_rate = self.domain_rates[domain]
                new_rate = old_rate / self.backoff_multiplier
                self.domain_rates[domain] = new_rate
                
                self.logger.warning(
                    "Adapting rate limit due to errors",
                    domain=domain,
                    error_rate=error_rate,
                    old_rate=old_rate,
                    new_rate=new_rate
                )
    
    def report_success(self, domain: str) -> None:
        """Report successful request for potential rate recovery
        
        Args:
            domain: Domain that responded successfully
        """
        # Could implement gradual rate recovery here
        pass
    
    def get_domain_stats(self, domain: str) -> Dict[str, any]:
        """Enhanced stats with adaptive information"""
        stats = super().get_domain_stats(domain)
        
        total_requests = self.request_counts[domain]
        error_count = self.error_counts[domain]
        
        stats.update({
            "error_count": error_count,
            "error_rate": (error_count / total_requests) if total_requests > 0 else 0.0,
            "domain_specific_rate": self.domain_rates[domain],
            "is_rate_adapted": self.domain_rates[domain] != self.requests_per_second
        })
        
        return stats