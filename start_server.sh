#!/bin/bash
# Enhanced MCP Server Startup Script
# Starts the Recipe Discovery MCP server with integrated search URL discovery and caching

echo "🚀 Starting Enhanced Recipe Discovery MCP Server..."
echo "📁 Project: ekitchen-ingestion"
echo "🔧 Features: Search URL Discovery + Caching + Smart Extraction"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

echo "🎯 Starting MCP server..."
echo "💡 The server now includes:"
echo "   • Search URL caching for faster discovery"
echo "   • Automatic search URL discovery for new sites" 
echo "   • Smart extraction integrated into the discovery pipeline"
echo "   • Enhanced workflow consolidating all tools"
echo ""
echo "🔗 Connect Claude to: stdio transport"
echo "📊 Use 'get_search_url_cache_stats' tool to see cache utilization"
echo ""

# Start the server
python3 run_mcp_server.py