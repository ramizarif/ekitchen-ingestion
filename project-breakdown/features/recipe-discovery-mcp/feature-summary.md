# Feature: Recipe Discovery MCP

**Status**: Planned
**Created**: 2025-07-20
**Priority**: Critical (Foundation for entire ingestion system)

## Feature Overview

### User Value
Enables conversational recipe discovery through Claude Desktop, allowing users to say "Find 1000 Mediterranean recipes and extract them" and have the system handle multi-site scraping, error recovery, and progress reporting automatically.

### User Interactions
- Natural language requests through Claude Desktop: "Scrape 500 Italian recipes from major cooking sites"
- Real-time progress updates during batch operations
- Automatic error recovery and retry with intelligent reporting
- Configurable site lists and scraping parameters

### Core Functionality
Multi-site web scraping system using recipe-scrapers library with FastMCP framework, async operations, comprehensive error handling, and batch processing for multiple recipe sites with progress reporting.

## Architecture Integration

### Fits Project Vision
Perfectly aligns with eKitchen's MCP-powered conversational data processing approach. This is the first major MCP server in the system and establishes patterns for:
- FastMCP async server architecture
- AI orchestration of complex data workflows
- Batch processing with intelligent error recovery
- Conversational interface for technical operations

### Integration Points
- **Input**: Natural language requests through Claude Desktop
- **Processing**: FastMCP server with async multi-site scraping
- **Output**: Structured recipe JSON for downstream eKitchen Database MCP
- **Monitoring**: Real-time progress reporting to Claude conversation

### Technical Approach
- **FastMCP Framework**: Async MCP server with stdio transport
- **Multi-site Architecture**: Parallel scraping with site-specific configuration
- **Error Isolation**: Individual site failures don't impact overall operation
- **Progress Tracking**: Real-time updates with completion estimates

### Patterns Used
- **MCP Server Structure**: FastMCP with async functions, comprehensive error handling
- **Async Operations**: Proper session management and resource cleanup
- **Batch Processing**: Efficient concurrent operations with progress reporting
- **Conversational Interface**: Natural language orchestration of complex workflows

## Scope Definition

### Essential Features
1. **Python Scraping Library Integration** - Research and integrate optimal scraping library
2. **FastMCP Server Foundation** - Basic server with stdio transport and error handling
3. **Recipe Scraping Integration** - Async wrapper around chosen library
4. **Multi-site Discovery Engine** - Parallel scraping across multiple sites

### Nice-to-Have Features (Future Phases)
- Advanced error recovery with intelligent retry strategies
- Recipe quality scoring and validation
- Custom site scrapers for non-standard sites
- Recipe deduplication and similarity detection
- Performance optimization and caching

### Explicit Non-Scope
- **Real-time Processing**: Focus on batch operations, not streaming
- **Custom AI Training**: Use existing libraries, not custom models
- **Database Storage**: Output JSON for eKitchen Database MCP to handle
- **User Interface**: Claude Desktop conversation is the interface

## Discovery Summary

### Questions Asked
No additional questions were needed - the user provided comprehensive feature description including:
- Specific technology choices (recipe-scrapers library, FastMCP framework)
- Architectural requirements (async operations, error handling)
- Performance expectations (batch processing, progress reporting)
- Integration context (multi-site web scraping system)

### Key Insights
1. **Library Research is Critical**: Choice of scraping library affects entire architecture
2. **Async Integration Complexity**: Wrapping sync scraping library for async MCP server
3. **Site-Specific Handling**: Different recipe sites require different approaches
4. **Error Isolation Important**: One site failure shouldn't break entire operation
5. **Progress Reporting Essential**: Long-running operations need real-time feedback

### Assumptions Made
- recipe-scrapers library will be the primary choice (pending research validation)
- FastMCP patterns from project architecture will be sufficient
- Stdio transport adequate for Claude Desktop communication
- Batch processing approach aligns with eKitchen ingestion use case

### Open Questions
- Specific rate limiting requirements for different recipe sites
- Memory usage patterns for large batch operations
- Integration approach with downstream eKitchen Database MCP
- Testing strategy for respectful site scraping