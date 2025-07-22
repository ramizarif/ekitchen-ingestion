"""Configuration management for Spoonacular API client"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import structlog

logger = structlog.get_logger()


@dataclass
class SpoonacularConfig:
    """Configuration for Spoonacular API client
    
    Loads configuration from JSON file with secure API key management.
    """
    
    api_key: str
    base_url: str = "https://api.spoonacular.com"
    requests_per_minute: int = 150
    requests_per_day: int = 5000
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


def load_config(config_path: Optional[str] = None) -> SpoonacularConfig:
    """Load Spoonacular configuration from JSON file
    
    Args:
        config_path: Path to config file, defaults to config/spoonacular.json
        
    Returns:
        SpoonacularConfig instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If API key is missing or invalid
    """
    if config_path is None:
        # Default to config/spoonacular.json relative to project root
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config" / "spoonacular.json"
    
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(
            f"Spoonacular config file not found: {config_file}. "
            "Please create config/spoonacular.json with your API key."
        )
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    
    # Validate API key
    api_key = config_data.get('api_key', '').strip()
    if not api_key or api_key == "YOUR_SPOONACULAR_API_KEY_HERE":
        raise ValueError(
            "Please set a valid Spoonacular API key in config/spoonacular.json. "
            "Get your API key from https://spoonacular.com/food-api"
        )
    
    # Create config with defaults for missing values
    config = SpoonacularConfig(
        api_key=api_key,
        base_url=config_data.get('base_url', 'https://api.spoonacular.com'),
        requests_per_minute=config_data.get('rate_limit', {}).get('requests_per_minute', 150),
        requests_per_day=config_data.get('rate_limit', {}).get('requests_per_day', 5000),
        request_timeout=config_data.get('request_timeout', 30),
        max_retries=config_data.get('max_retries', 3),
        retry_delay=config_data.get('retry_delay', 1.0)
    )
    
    logger.info("Spoonacular config loaded successfully", 
                base_url=config.base_url,
                rate_limit_rpm=config.requests_per_minute)
    
    return config


def get_config(config_path: Optional[str] = None) -> SpoonacularConfig:
    """Get cached configuration instance
    
    Loads configuration once and caches it for subsequent calls.
    
    Args:
        config_path: Path to config file, defaults to config/spoonacular.json
        
    Returns:
        SpoonacularConfig instance
    """
    if not hasattr(get_config, '_cached_config'):
        get_config._cached_config = load_config(config_path)
    
    return get_config._cached_config