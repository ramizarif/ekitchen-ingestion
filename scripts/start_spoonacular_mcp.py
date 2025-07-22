#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Startup script for Spoonacular MCP Server

Launches the Spoonacular MCP server for Claude Desktop integration.
Follows the established project patterns for MCP server startup.
"""

import asyncio
import sys
import os
import structlog
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """Setup structured logging for the MCP server"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def validate_configuration():
    """Validate Spoonacular configuration before starting server"""
    try:
        from spoonacular_mcp.config import get_config
        config = get_config()
        
        if not config.api_key:
            print("ERROR: Spoonacular API key not configured")
            print("   Please check config/spoonacular.json")
            return False
            
        print(f"Configuration validated")
        print(f"   Server: {config.server_name}")
        print(f"   API URL: {config.base_url}")
        print(f"   Rate limit: {config.requests_per_minute}/minute")
        
        return True
        
    except Exception as e:
        print(f"Configuration error: {e}")
        return False

def main():
    """Main entry point for Spoonacular MCP server"""
    print("Starting Spoonacular MCP Server...")
    print("   Provides conversational AI interface for Spoonacular ingredient data")
    print()
    
    # Setup logging
    setup_logging()
    logger = structlog.get_logger()
    
    # Validate configuration
    if not validate_configuration():
        sys.exit(1)
    
    print("Initializing server components...")
    
    try:
        # Import and start the MCP server
        from spoonacular_mcp.server import main as server_main
        
        print("Server components initialized")
        print("Starting Spoonacular MCP server...")
        print("   Available tools:")
        print("   - search_ingredient(name, limit) - Search for ingredients")
        print("   - get_ingredient(ingredient_id, amount, unit) - Get detailed nutrition info")
        print("   - get_ingredient_substitutes(ingredient_id) - Find ingredient substitutes")
        print("   - health_check() - Server health status")
        print("   - test_connectivity() - Test API connectivity")
        print()
        print("Ready for Claude Desktop connection...")
        print("   Configure in Claude Desktop with this script path")
        print()
        
        # Log startup
        logger.info(
            "Spoonacular MCP server starting",
            server_type="spoonacular_mcp",
            tools_available=["search_ingredient", "get_ingredient", "get_ingredient_substitutes"]
        )
        
        # Start the server (this will block)
        server_main()
        
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        logger.info("Spoonacular MCP server stopped by user")
        
    except Exception as e:
        print(f"\nServer error: {e}")
        logger.error("Spoonacular MCP server error", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()