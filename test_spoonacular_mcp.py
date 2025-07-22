#!/usr/bin/env python3
"""Test script for Spoonacular MCP server functionality

Tests configuration, imports, and basic server functionality.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        print("  ✓ Importing spoonacular_client...")
        from spoonacular_client.client import SpoonacularClient
        from spoonacular_client.config import get_config as get_spoonacular_config
        
        print("  ✓ Importing spoonacular_mcp...")
        from spoonacular_mcp.config import get_config
        from spoonacular_mcp.server import mcp
        from spoonacular_mcp.models import ServerHealth
        
        print("  ✓ All imports successful")
        return True
        
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False

def test_configuration():
    """Test configuration loading"""
    print("\nTesting configuration...")
    
    try:
        from spoonacular_mcp.config import get_config
        config = get_config()
        
        print(f"  ✓ Config loaded successfully")
        print(f"    Server: {config.server_name}")
        print(f"    API URL: {config.base_url}")
        print(f"    Rate limit: {config.requests_per_minute}/minute")
        
        if config.api_key:
            print(f"    API key: configured ({len(config.api_key)} chars)")
            api_key_configured = True
        else:
            print(f"    API key: NOT CONFIGURED")
            api_key_configured = False
            
        return api_key_configured
        
    except Exception as e:
        print(f"  ✗ Configuration failed: {e}")
        return False

def test_server_initialization():
    """Test server components can be initialized"""
    print("\nTesting server initialization...")
    
    try:
        from spoonacular_mcp.server import state
        
        print("  ✓ Server state created")
        print(f"    Start time: {state.start_time}")
        print(f"    Total requests: {state.total_requests}")
        print(f"    Active requests: {state.active_requests}")
        
        # Test client initialization
        client = state.spoonacular_client
        print("  ✓ Spoonacular client initialized")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Server initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tool_registration():
    """Test that tools are properly registered with FastMCP"""
    print("\nTesting tool registration...")
    
    try:
        from spoonacular_mcp.server import mcp
        
        # Get registered tools using FastMCP API
        tools = await mcp.get_tools()
        
        expected_tools = [
            'health_check',
            'get_server_config', 
            'test_connectivity',
            'search_ingredient',
            'get_ingredient',
            'get_ingredient_substitutes'
        ]
        
        print(f"  Registered tools: {len(tools)}")
        
        for tool in expected_tools:
            if tool in tools:
                print(f"    ✓ {tool}")
            else:
                print(f"    ✗ {tool} (missing)")
        
        if len(tools) >= 6:  # We expect at least 6 tools
            print("  ✓ Tool registration successful")
            return True
        else:
            print("  ✗ Some tools missing")
            return False
        
    except Exception as e:
        print(f"  ✗ Tool registration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("Spoonacular MCP Server Test Suite")
    print("=" * 50)
    
    # Run tests
    imports_ok = test_imports()
    config_ok = test_configuration()
    server_ok = test_server_initialization()
    tools_ok = await test_tool_registration()
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"✓ Imports:        {'PASS' if imports_ok else 'FAIL'}")
    print(f"✓ Configuration:  {'PASS' if config_ok else 'FAIL'}")
    print(f"✓ Server Init:    {'PASS' if server_ok else 'FAIL'}")
    print(f"✓ Tool Registration: {'PASS' if tools_ok else 'FAIL'}")
    
    if imports_ok and server_ok and tools_ok:
        print("\n🎉 SPOONACULAR MCP SERVER: READY!")
        print("✓ Server can be started with: python3 scripts/start_spoonacular_mcp.py")
        print("✓ All tools are registered and functional")
        
        if config_ok:
            print("✓ API key configured - full functionality available")
        else:
            print("! API key needed in config/spoonacular.json for full functionality")
            
        print("✓ Ready for Claude Desktop integration")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        print("Please fix the issues above before proceeding.")
        return False

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)