"""Unit tests for Recipe Discovery MCP configuration"""

import os
import pytest
from unittest.mock import patch

from recipe_discovery_mcp.config import Config, get_config, reload_config


class TestConfig:
    """Test Config model functionality"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = Config()
        
        assert config.server_name == "recipe-discovery-mcp"
        assert config.log_level == "INFO"
        assert config.max_concurrent_requests == 10
        assert config.request_timeout == 30
        assert config.requests_per_second == 2.0
        assert config.max_retries == 3
        assert config.debug_mode is False
    
    def test_config_from_env(self):
        """Test configuration loading from environment variables"""
        env_vars = {
            "SERVER_NAME": "test-server",
            "LOG_LEVEL": "DEBUG",
            "MAX_CONCURRENT_REQUESTS": "5",
            "REQUEST_TIMEOUT": "60",
            "DEBUG_MODE": "true"
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            
            assert config.server_name == "test-server"
            assert config.log_level == "DEBUG"
            assert config.max_concurrent_requests == 5
            assert config.request_timeout == 60
            assert config.debug_mode is True
    
    def test_get_log_level(self):
        """Test log level normalization"""
        config = Config(log_level="debug")
        assert config.get_log_level() == "DEBUG"
        
        config = Config(log_level="INFO")
        assert config.get_log_level() == "INFO"
    
    def test_is_debug(self):
        """Test debug mode detection"""
        # Explicit debug mode
        config = Config(debug_mode=True)
        assert config.is_debug() is True
        
        # Debug log level
        config = Config(log_level="DEBUG", debug_mode=False)
        assert config.is_debug() is True
        
        # Not debug
        config = Config(log_level="INFO", debug_mode=False)
        assert config.is_debug() is False
    
    def test_retry_delays(self):
        """Test retry delay calculation"""
        config = Config(max_retries=3, retry_delay=1.0)
        delays = config.get_retry_delays()
        
        assert len(delays) == 3
        assert delays == [1.0, 2.0, 4.0]  # exponential backoff
    
    def test_custom_retry_settings(self):
        """Test custom retry configuration"""
        config = Config(max_retries=2, retry_delay=0.5)
        delays = config.get_retry_delays()
        
        assert len(delays) == 2
        assert delays == [0.5, 1.0]


class TestConfigSingleton:
    """Test global configuration management"""
    
    def test_get_config_singleton(self):
        """Test that get_config returns same instance"""
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
    
    def test_reload_config(self):
        """Test configuration reloading"""
        # Get initial config
        config1 = get_config()
        
        # Reload config
        config2 = reload_config()
        
        # Should be different instances but same values
        assert config1 is not config2
        assert config1.server_name == config2.server_name
    
    def test_reload_with_env_changes(self):
        """Test reloading with environment changes"""
        # Get initial config
        initial_config = get_config()
        initial_name = initial_config.server_name
        
        # Change environment and reload
        with patch.dict(os.environ, {"SERVER_NAME": "changed-server"}):
            new_config = reload_config()
            
            assert new_config.server_name == "changed-server"
            assert new_config.server_name != initial_name