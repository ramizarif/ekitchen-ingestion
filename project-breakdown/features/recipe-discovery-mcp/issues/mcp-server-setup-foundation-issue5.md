# Issue #5: MCP Server Setup and Foundation

**Status**: ✅ Done
**Assigned**: Engineering Agent (to be spawned)  
**Priority**: Critical (Foundation for all recipe discovery functionality)  
**Estimated Effort**: 4-6 hours  

## Prerequisites Completed ✅
- **Issue #4**: Python Scraping Library Research - ✅ COMPLETED
  - recipe-scrapers library approved for production use
  - FastMCP integration patterns validated
  - Async wrapper approach proven effective

## Issue Overview

Initialize the core FastMCP server infrastructure for Recipe Discovery MCP with async configuration, comprehensive error handling, and stdio transport for Claude Desktop integration.

## Implementation Plan

### Step 1: Project Structure Setup (30 minutes)
```bash
# Create directory structure
mkdir -p recipe_discovery_mcp/utils
mkdir -p tests/unit
mkdir -p tests/integration

# Core files to create
recipe_discovery_mcp/
├── __init__.py
├── server.py              # Main FastMCP server
├── config.py              # Configuration management
├── models.py              # Data models (RecipeData, etc.)
└── utils/
    ├── __init__.py
    ├── logging.py          # Structured logging
    └── error_handling.py   # Error handling framework
```

### Step 2: Dependencies and Environment (20 minutes)
Create `requirements.txt` with core dependencies from Issue #4 research:
```txt
fastmcp>=0.9.0
recipe-scrapers>=15.8.0
asyncio-extras
pydantic>=2.0.0
python-dotenv
structlog
```

Create `.env.example` for configuration:
```env
# MCP Server Configuration
MCP_SERVER_NAME=recipe-discovery-mcp
LOG_LEVEL=INFO
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30

# Rate Limiting
REQUESTS_PER_SECOND=2
MAX_RETRIES=3
```

### Step 3: FastMCP Server Foundation (90 minutes)
Implement `server.py` using patterns from project-breakdown/master.md:

#### Core Server Structure
```python
import asyncio
import logging
from typing import Dict, List, Any
from fastmcp import FastMCP
from fastmcp.tools import tool

from .config import Config
from .models import RecipeData
from .utils.error_handling import handle_scraping_errors
from .utils.logging import setup_structured_logging

class RecipeDiscoveryMCP:
    def __init__(self, config: Config):
        self.config = config
        self.server = FastMCP("Recipe Discovery MCP")
        self.setup_tools()
        
    def setup_tools(self):
        """Register all MCP tools"""
        # Placeholder tools - actual scraping in Issue #6
        pass
        
    async def start(self):
        """Start the MCP server with stdio transport"""
        # Implementation details...
```

#### Key Components to Implement:
1. **Async Event Loop Management** - Proper startup/shutdown
2. **Stdio Transport Configuration** - Claude Desktop communication
3. **Error Handling Framework** - Comprehensive exception management
4. **Health Check Tool** - Server status monitoring
5. **Configuration Loading** - Environment-based settings

### Step 4: Configuration Management (45 minutes)
Implement `config.py` following eKitchen patterns:

```python
from pydantic import BaseSettings
from typing import Optional

class Config(BaseSettings):
    # MCP Server Settings
    server_name: str = "recipe-discovery-mcp"
    log_level: str = "INFO"
    
    # Performance Settings
    max_concurrent_requests: int = 10
    request_timeout: int = 30
    
    # Rate Limiting
    requests_per_second: float = 2.0
    max_retries: int = 3
    
    class Config:
        env_file = ".env"
```

### Step 5: Error Handling Framework (60 minutes)
Implement `utils/error_handling.py`:

#### Error Categories
- **Network Errors**: Connection failures, timeouts
- **Parsing Errors**: Invalid HTML, missing recipe data
- **Rate Limiting**: Too many requests
- **Configuration Errors**: Invalid settings

#### Error Handling Pattern
```python
from typing import Union, Callable, Any
import structlog

logger = structlog.get_logger()

async def handle_scraping_errors(func: Callable) -> Callable:
    """Decorator for comprehensive error handling"""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Log error with context
            # Return structured error response
            # Implement retry logic
    return wrapper
```

### Step 6: Structured Logging (45 minutes)
Implement `utils/logging.py`:

#### Logging Requirements
- **Structured JSON logs** for production
- **Human-readable logs** for development
- **Request tracing** for debugging
- **Performance metrics** for monitoring

### Step 7: Data Models (30 minutes)
Implement `models.py` based on Issue #4 research:

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class RecipeData(BaseModel):
    """Standard recipe data structure"""
    url: str
    title: Optional[str] = None
    ingredients: List[str] = []
    instructions: str = ""
    total_time: Optional[int] = None  # minutes
    yields: Optional[str] = None
    image_url: Optional[str] = None
    
    # Metadata
    scraped_at: datetime
    success: bool = True
    error: Optional[str] = None
    
    def to_json(self) -> Dict[str, Any]:
        """Serialize for downstream processing"""
        return self.dict()
```

### Step 8: Basic Tools Implementation (45 minutes)
Implement placeholder MCP tools for testing:

#### Health Check Tool
```python
@tool("health_check")
async def health_check() -> Dict[str, Any]:
    """Check MCP server health and configuration"""
    return {
        "status": "healthy",
        "server_name": config.server_name,
        "timestamp": datetime.now().isoformat()
    }
```

#### Configuration Tool
```python
@tool("get_server_config")
async def get_server_config() -> Dict[str, Any]:
    """Get current server configuration"""
    return {
        "max_concurrent": config.max_concurrent_requests,
        "timeout": config.request_timeout,
        "rate_limit": config.requests_per_second
    }
```

### Step 9: Testing Setup (60 minutes)
Create basic test structure:

#### Unit Tests
- Configuration loading
- Error handling decorators
- Data model validation
- Logging setup

#### Integration Tests
- MCP server startup/shutdown
- Tool registration and calling
- stdio transport communication

### Step 10: Documentation and Validation (30 minutes)
- Update README with setup instructions
- Create development guide
- Validate all tools work with Claude Desktop
- Prepare for Issue #6 integration

## Acceptance Criteria

### Functional Requirements ✅
- [ ] FastMCP server starts successfully with stdio transport
- [ ] Health check tool responds correctly
- [ ] Configuration loading works from environment variables
- [ ] Error handling framework catches and logs all exceptions
- [ ] Structured logging outputs proper JSON format
- [ ] All MCP tools are registered and discoverable by Claude

### Technical Requirements ✅
- [ ] Follows FastMCP async/await patterns
- [ ] Implements comprehensive error handling
- [ ] Uses structured logging with proper levels
- [ ] Configuration is environment-based with defaults
- [ ] Code follows eKitchen project patterns
- [ ] All dependencies properly managed

### Integration Requirements ✅
- [ ] Successfully communicates with Claude Desktop via stdio
- [ ] Can be imported and extended by Issue #6
- [ ] Ready for recipe-scrapers library integration
- [ ] Supports concurrent request handling
- [ ] Proper resource cleanup on shutdown

### Quality Requirements ✅
- [ ] Code coverage >80% for core functionality
- [ ] All error conditions properly handled
- [ ] Performance metrics logged appropriately
- [ ] Documentation complete and accurate
- [ ] Follows established patterns from project-breakdown/

## Integration Notes

### Builds On Issue #4 ✅
- Uses recipe-scrapers library as approved
- Implements FastMCP async wrapper patterns
- Follows error handling strategies validated

### Prepares For Issue #6 🔄
- Server foundation ready for scraping integration
- Data models match recipe-scrapers output format
- Error handling supports batch operations
- Configuration supports rate limiting needs

### Aligns With Project Architecture ✅
- MCP-powered conversational data processing
- Async operations with comprehensive error handling
- Structured data flow with JSON serialization
- Natural language orchestration readiness

## Development Notes

### Key Files Modified/Created
```
recipe_discovery_mcp/
├── __init__.py                    ✅ Create
├── server.py                      ✅ Create
├── config.py                      ✅ Create
├── models.py                      ✅ Create
└── utils/
    ├── __init__.py               ✅ Create
    ├── logging.py                ✅ Create
    └── error_handling.py         ✅ Create

requirements.txt                   ✅ Create
.env.example                      ✅ Create
tests/                            ✅ Create
```

### Performance Expectations
- **Startup Time**: <2 seconds
- **Tool Response**: <100ms for health checks
- **Memory Usage**: <50MB baseline
- **Concurrent Capacity**: 10+ simultaneous tools calls

### Error Handling Coverage
- Network connectivity issues
- Invalid configuration
- MCP protocol errors
- Resource cleanup failures
- Graceful degradation scenarios

---

**Ready for Engineering Agent Assignment**  
**All prerequisites completed, clear implementation plan provided**  
**Expected completion: 4-6 hours**  
**Board Sync 2025-07-20 01:36**: Status updated from GitHub board - Done → Done
