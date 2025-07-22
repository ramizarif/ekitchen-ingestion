# Feature: Nutrition Enrichment with Spoonacular MCP

**Status**: Planned  
**Created**: 2025-07-21  
**Priority**: High

## Feature Overview

### User Value
Provides rich nutritional data for ingredients and recipes through AI-orchestrated conversations like *"Enrich these 500 recipes with nutritional data from Spoonacular"* instead of manual data entry or complex pipeline management.

### User Interactions
- AI-orchestrated batch processing through conversational interface
- Natural language commands for ingredient enrichment
- Progress tracking and cost monitoring during bulk operations
- Error recovery through conversational debugging

### Core Functionality
- Integrate Spoonacular API through dedicated MCP server
- Enrich `global_ingredients` table with comprehensive nutrition data
- Calculate recipe-level nutrition for `global_recipes` table  
- Handle ingredient variations and deduplication intelligently
- Provide cost-aware processing with rate limiting

## Architecture Integration

### Fits Project Vision
Aligns perfectly with the AI-powered conversational data processing approach. This becomes the third MCP server in the pipeline: Recipe Discovery → Database Processing → **Spoonacular Enrichment**.

### Integration Points
- **Input**: Ingredients from `global_ingredients` table needing enrichment
- **Processing**: Spoonacular API calls with intelligent batching and deduplication
- **Output**: Enhanced nutrition data in database tables
- **Orchestration**: Claude Desktop conversations for workflow management

### Technical Approach
- FastMCP server following established project patterns
- Async operations with comprehensive error handling
- PostgreSQL integration (potentially through PostgreSQL MCP)
- Rate limiting and cost optimization
- Batch processing with progress reporting

### Patterns Used
- **MCP Server Structure**: FastMCP with async functions, comprehensive error handling
- **AI Integration**: Large context processing for batch operations
- **Database Operations**: Bulk operations with transactional consistency
- **Conversational Workflows**: Natural language orchestration over programmatic pipelines

## Scope Definition

### Essential Features
- Spoonacular API integration through MCP server
- Ingredient nutrition data enrichment
- Recipe nutrition calculation and aggregation
- Database integration with existing eKitchen schema
- Rate limiting and error handling

### Nice-to-Have Features
- Ingredient substitution recommendations
- Recipe quality scoring based on nutrition completeness
- Cost optimization strategies and reporting
- Advanced caching for frequently used ingredients

### Explicit Non-Scope
- Custom nutrition database (using Spoonacular as primary source)
- Real-time nutrition calculations (batch processing sufficient)
- Complex recipe analysis beyond basic nutrition aggregation

## Discovery Summary

### Questions Asked
User preferred to create individual issues rather than use suggested breakdown.

### Key Insights
- Feature fits naturally into established MCP architecture
- Database schema already designed for nutrition enrichment
- Conversational approach preferred over traditional ETL patterns
- Cost awareness important for API-based enrichment

### Assumptions Made
- Spoonacular API will be primary nutrition data source
- PostgreSQL MCP may be used for database operations
- Batch processing approach suitable for data enrichment use case
- AI orchestration through Claude Desktop conversations

### Open Questions
- Specific Spoonacular API endpoints to prioritize
- Database operation patterns (direct SQL vs MCP integration)  
- Error recovery strategies for failed enrichments
- Cost optimization and monitoring approaches