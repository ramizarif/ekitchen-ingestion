#!/usr/bin/env python3
"""
Entry point for Recipe Discovery MCP Server with enhanced logging
"""

import sys
import os
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up file logging before importing the server
log_file = f"mcp_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)  # Also log to stderr for Claude
    ]
)

# Log startup
logger = logging.getLogger(__name__)
logger.info(f"Starting MCP server with logging to {log_file}")

# Import and run the server
if __name__ == "__main__":
    try:
        from recipe_discovery_mcp.server import main
        logger.info("Server module imported successfully")
        main()
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)