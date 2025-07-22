"""Configuration management for Spoonacular MCP server

Loads configuration from the existing Spoonacular client config
and provides MCP-specific settings.
"""

import os
from typing import Optional
from dataclasses import dataclass

from ..spoonacular_client.config import get_config as get_spoonacular_config, SpoonacularConfig


@dataclass
class SpoonacularMCPConfig:
    """Configuration for Spoonacular MCP server"""
    
    # Spoonacular API settings (inherited from client)
    api_key: str
    base_url: str
    requests_per_minute: int
    request_timeout: float
    max_retries: int
    retry_delay: float
    
    # MCP server specific settings
    server_name: str = "Spoonacular MCP"
    log_level: str = "INFO"
    enable_metrics: bool = True
    max_concurrent_requests: int = 10
    
    @classmethod
    def from_spoonacular_config(cls, spoonacular_config: SpoonacularConfig) -> 'SpoonacularMCPConfig':
        """Create MCP config from Spoonacular client config"""
        return cls(
            api_key=spoonacular_config.api_key,
            base_url=spoonacular_config.base_url,
            requests_per_minute=spoonacular_config.requests_per_minute,
            request_timeout=spoonacular_config.request_timeout,
            max_retries=spoonacular_config.max_retries,
            retry_delay=spoonacular_config.retry_delay,
            server_name=os.getenv("SPOONACULAR_MCP_SERVER_NAME", "Spoonacular MCP"),
            log_level=os.getenv("SPOONACULAR_MCP_LOG_LEVEL", "INFO"),
            enable_metrics=os.getenv("SPOONACULAR_MCP_ENABLE_METRICS", "true").lower() == "true",
            max_concurrent_requests=int(os.getenv("SPOONACULAR_MCP_MAX_CONCURRENT", "10"))
        )
    
    def is_debug(self) -> bool:
        """Check if debug mode is enabled"""
        return self.log_level.upper() == "DEBUG"


def get_config() -> SpoonacularMCPConfig:
    """Get MCP configuration, inheriting from Spoonacular client config
    
    Returns:
        SpoonacularMCPConfig: MCP server configuration
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Get the base Spoonacular client configuration
    spoonacular_config = get_spoonacular_config()
    
    # Create MCP config from it
    mcp_config = SpoonacularMCPConfig.from_spoonacular_config(spoonacular_config)
    
    return mcp_config