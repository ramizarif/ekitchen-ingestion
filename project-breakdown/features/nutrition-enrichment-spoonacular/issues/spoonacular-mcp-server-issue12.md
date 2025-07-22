# Issue #12: Create Spoonacular MCP Server with Ingredient Tools

**Status**: 🔄 In Progress  
**Priority**: High  
**Type**: Feature  
**Effort**: Medium-Large (6-8 hours)  
**GitHub**: [Issue #12](https://github.com/ramizarif/ekitchen-ingestion/issues/12)  
**Dependencies**: Issue #11 (Spoonacular API Client must be completed first)

## Overview
Create a Spoonacular MCP server following the established Recipe Discovery MCP patterns. The server will provide three AI-orchestrated tools for ingredient search, information retrieval, and substitute discovery. This enables conversational nutrition workflows like "find the nutritional values for butter and any substitutes for the ingredient".

## Implementation Plan

### Step 1: MCP Server Foundation
```bash
# Create MCP server structure following recipe_discovery_mcp pattern
mkdir -p spoonacular_mcp
mkdir -p scripts
touch spoonacular_mcp/__init__.py
touch spoonacular_mcp/server.py
touch spoonacular_mcp/tools.py  
touch spoonacular_mcp/config.py
touch spoonacular_mcp/models.py
touch scripts/start_spoonacular_mcp.py
```

### Step 2: Server Implementation
- Follow exact patterns from `recipe_discovery_mcp/server.py`
- FastMCP server initialization with proper error handling
- Async tool registration framework
- Health check and monitoring endpoints
- Logging configuration for debugging

### Step 3: Three MCP Tools Implementation

#### Tool 1: Search Ingredient
- Search ingredients by name using Spoonacular search endpoint
- Return structured results with ingredient IDs and names
- Enable Claude to find ingredients for further processing

#### Tool 2: Get Ingredient Information  
- Retrieve detailed ingredient data using Spoonacular ID
- Include nutrition facts per 100g or specified amount
- Provide comprehensive ingredient information for Claude

#### Tool 3: Get Ingredient Substitutes
- Find substitute suggestions for given ingredient ID
- Return structured list of alternatives
- Enable Claude to suggest ingredient replacements

### Step 4: Claude Desktop Integration
- Create startup script following project patterns
- Configure MCP server for Claude Desktop connection
- Test conversational workflows with complex queries
- Ensure tool descriptions enable AI orchestration

### Step 5: Error Handling & Validation
- Comprehensive async error handling throughout
- Proper MCP protocol error responses
- Graceful handling of API failures and rate limits
- Useful debugging information for troubleshooting

## Technical Requirements

### MCP Server Architecture
- Follow FastMCP patterns from Recipe Discovery MCP exactly
- Async tool implementations with proper type hints
- Structured tool descriptions for Claude understanding
- Error handling that provides useful feedback

### Tool Signatures
```python
@server.tool()
async def search_ingredient(name: str, limit: int = 10) -> dict:
    """Search for ingredients by name using Spoonacular API"""

@server.tool()
async def get_ingredient(ingredient_id: int, amount: float = 100, unit: str = "grams") -> dict:
    """Get detailed ingredient information including nutrition facts"""

@server.tool()
async def get_ingredient_substitutes(ingredient_id: int) -> dict:
    """Get substitute suggestions for an ingredient"""
```

### Conversational Integration
The MCP should enable Claude to handle complex requests like:
- "Find the nutritional values for butter and any substitutes for the ingredient"
- "Search for chicken breast, get its nutrition info, and find alternatives"
- "What are the nutrition facts for olive oil and what can I substitute it with?"

## Acceptance Criteria
- [ ] MCP server follows Recipe Discovery MCP patterns exactly
- [ ] Three tools implemented and working with Spoonacular API client
- [ ] Server connects to Claude Desktop successfully
- [ ] Claude can execute complex multi-step ingredient workflows
- [ ] Tool responses structured for AI consumption
- [ ] Error handling provides useful feedback through MCP protocol
- [ ] Startup script works reliably

### Conversational Testing
- [ ] Claude executes: "Find nutritional values for butter and any substitutes"
- [ ] Complex ingredient workflows work seamlessly
- [ ] Error scenarios handled gracefully in conversation
- [ ] Tool descriptions enable Claude to choose correct tools

## Dependencies
- **Critical**: Issue #11 must be completed first (Spoonacular API client required)
- FastMCP framework installed and working
- Spoonacular API key configured from Issue #11
- Claude Desktop setup for MCP connections

## Integration Context
This MCP server transforms the standalone API client from Issue #11 into a conversational AI tool. It will complement the Recipe Discovery MCP and enable end-to-end nutrition enrichment workflows.

## Definition of Done
- Working Spoonacular MCP server following established patterns
- All three tools functional with Spoonacular API integration
- Claude Desktop successfully connects and uses tools
- Complex conversational workflows demonstrated
- Documentation complete with setup instructions
- Ready for database integration in future issues

---
*This issue depends on Issue #11 completion and follows the established MCP server patterns for conversational AI integration.*