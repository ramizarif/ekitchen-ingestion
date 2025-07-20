"""Configuration management for Recipe Discovery MCP Server"""

import os
from typing import Optional
from pydantic import BaseSettings, Field


class Config(BaseSettings):
    """Server configuration with environment variable support
    
    Loads configuration from environment variables with sensible defaults.
    Follows eKitchen patterns for configuration management.
    """
    
    # MCP Server Settings
    server_name: str = Field(
        default="recipe-discovery-mcp",
        description="Name of the MCP server"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    # Performance Settings
    max_concurrent_requests: int = Field(
        default=10,
        description="Maximum number of concurrent scraping requests"
    )
    request_timeout: int = Field(
        default=30,
        description="Timeout for individual requests in seconds"
    )
    
    # Rate Limiting Settings
    requests_per_second: float = Field(
        default=2.0,
        description="Maximum requests per second to prevent rate limiting"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed requests"
    )
    retry_delay: float = Field(
        default=1.0,
        description="Base delay between retries in seconds"
    )
    
    # User Agent for HTTP requests
    user_agent: str = Field(
        default="eKitchen Recipe Discovery Bot 1.0 (Respectful scraping for culinary data)",
        description="User agent string for HTTP requests"
    )
    
    # Scraping Configuration (Issue #6)
    scraping_timeout: int = Field(
        default=30,
        description="Timeout for individual scraping requests in seconds"
    )
    max_concurrent_scrapes: int = Field(
        default=10,
        description="Maximum number of concurrent scraping operations"
    )
    respect_robots_txt: bool = Field(
        default=True,
        description="Whether to respect robots.txt files (not implemented yet)"
    )
    
    # Development/Production Settings
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging"
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable performance metrics collection"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = ""
    
    def get_log_level(self) -> str:
        """Get normalized log level"""
        return self.log_level.upper()
    
    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.debug_mode or self.log_level.upper() == "DEBUG"
    
    def get_retry_delays(self) -> list[float]:
        """Generate retry delay sequence with exponential backoff"""
        delays = []
        for i in range(self.max_retries):
            delays.append(self.retry_delay * (2 ** i))
        return delays


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance
    
    Implements singleton pattern to ensure consistent configuration
    across the application.
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment
    
    Useful for testing or when configuration changes at runtime.
    """
    global _config
    _config = Config()
    return _config