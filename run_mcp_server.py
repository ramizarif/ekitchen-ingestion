#!/usr/bin/env python3
"""Entry point for Recipe Discovery MCP Server

This script properly initializes the Python path and starts the MCP server
for Claude Desktop integration.
"""

import sys
import os
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up file logging
log_file = f"mcp_server_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)
logger.info(f"=== MCP SERVER STARTING - Logs saved to {log_file} ===")

# Import and run the server
if __name__ == "__main__":
    try:
        from recipe_discovery_mcp.server import main
        logger.info("Starting Recipe Discovery MCP Server")
        main()
    except Exception as e:
        logger.error(f"Server startup failed: {e}", exc_info=True)
        sys.exit(1)