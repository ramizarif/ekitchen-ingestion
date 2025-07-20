# Project Master Plan - eKitchen Ingestion

**Last Updated**: January 19, 2025
**Version**: 1.0
**Next Review**: February 19, 2025

## Project Vision

### Core Purpose
Build an AI-powered recipe and ingredient ingestion system that transforms the eKitchen app from a basic kitchen management tool into an intelligent culinary platform with rich, production-ready data. Instead of complex queue-based pipelines, we use conversational AI with custom MCP (Model Context Protocol) servers to discover, standardize, enrich, and intelligently process recipe data from across the web.

The system enables conversations like: *"Find 1000 Italian recipes, enrich them with nutritional data, tag ingredients appropriately, and generate similarity mappings for recommendations"* - all through natural language rather than traditional ETL pipelines.

### Success Metrics
- **Data Quality**: 95%+ recipe parsing success rate across all major recipe sites
- **Enrichment Coverage**: 85%+ of ingredients successfully enriched with nutritional data
- **Processing Efficiency**: 1000 recipes processed end-to-end in under 30 minutes
- **Development Speed**: 75% faster implementation than traditional pipeline architecture
- **Cost Efficiency**: <$25/month operational costs for moderate usage (1000+ recipes/month)
- **User Experience**: Natural language recipe ingestion through conversational interface

### Target Users
- **Primary**: Solo developer (you) building production-ready recipe data for eKitchen
- **Secondary**: AI agents (Claude) that orchestrate complex data workflows through conversation
- **Future**: eKitchen app users who benefit from rich, intelligently categorized recipe content

## Architecture Overview

### System Architecture
**MCP-Powered Conversational Data Processing** - Replace traditional microservice pipelines with AI-orchestrated MCP servers that handle complex data workflows through natural language conversations.

**Core Decision**: Choose simplicity and intelligence over complexity. Let AI handle the complex logic (format variations, deduplication, tagging) while MCP servers provide clean integration points.

### Core Components
1. **Recipe Discovery MCP**: Multi-site web scraping using recipe-scrapers library
2. **eKitchen Database MCP**: AI-powered data processing and database operations  
3. **Spoonacular Integration MCP**: Intelligent ingredient enrichment with rate limiting
4. **Claude Desktop**: AI orchestration layer that coordinates workflows
5. **PostgreSQL Database**: Shared data store with existing eKitchen schema
6. **Optional: PostgreSQL MCP**: Direct SQL access for complex operations

### Technology Stack
- **AI Orchestration**: Claude Desktop with MCP integration
- **MCP Servers**: Python with FastMCP framework
- **Web Scraping**: recipe-scrapers library + BeautifulSoup + httpx
- **Database**: PostgreSQL (shared with existing eKitchen)
- **API Integration**: Spoonacular API for nutritional data
- **Development**: Local development with stdio transport

**Architectural Reasoning**: Python excels at data processing and AI integration, while Go (existing eKitchen) handles business logic. MCP provides clean separation and AI orchestration capabilities.

### Data Flow
```
Keywords → Recipe Discovery MCP → Raw JSON (50MB+) → 
eKitchen Database MCP (AI Processing) → Structured DB Records → 
Spoonacular MCP → Enriched Ingredients → 
Final Tagged & Categorized Recipe Data
```

**Key Innovation**: AI processes massive JSON in conversation context, making intelligent decisions about standardization, deduplication, and categorization in real-time.

## Feature Roadmap

### Active Features
- **Recipe Discovery MCP** (In Progress): Multi-site recipe scraping with recipe-scrapers
- **eKitchen Database MCP** (Planned Week 1): AI-powered recipe processing and database integration

### Planned Features
- **Spoonacular Integration MCP** (Week 1): Batch ingredient enrichment
- **AI Tagging System**: Automatic ingredient and recipe categorization
- **Ingredient Similarity Mapping**: AI-generated substitution relationships
- **Advanced Error Recovery**: Intelligent handling of failed enrichments
- **Recipe Quality Scoring**: AI assessment of recipe completeness and reliability

### Completed Features
None yet - project in initial development phase

### Deprioritized Features
- **Complex Queue Systems**: Too much operational overhead for data enrichment use case
- **Microservice Architecture**: Unnecessary complexity for single-developer project
- **Real-time Processing**: Batch processing sufficient for data enrichment needs
- **Custom AI Training**: Using existing LLMs more cost-effective than custom models

## Architectural Decisions

### Current Decisions
1. **MCP over Microservices**: Simpler, more flexible, AI-orchestrated vs. complex service mesh
2. **Conversational Workflows**: Natural language orchestration vs. programmatic pipelines
3. **AI-Powered Processing**: Let AI handle format variations vs. rigid parsing rules
4. **Python for Data Processing**: Language strength alignment vs. technology consistency
5. **Batch over Real-time**: Data enrichment use case vs. user-facing requirements

### Decision Evolution
- **Original Plan**: Complex multi-queue pipeline with separate AI processing service
- **Evolved Plan**: Simplified MCP architecture with AI processing integrated into database operations
- **Key Insight**: AI should handle intelligent decisions, not separate microservices

### Lessons Learned
- **Complexity is the Enemy**: For solo development, simplicity beats theoretical scalability
- **AI Changes Everything**: Traditional ETL patterns become unnecessary when AI can handle variability
- **MCP Enables New Patterns**: Conversational data processing is genuinely more powerful than pipelines

## Patterns & Best Practices

### Established Patterns
- **MCP Server Structure**: FastMCP with async functions, comprehensive error handling, clear tool descriptions
- **AI Integration**: Pass large JSON for context processing rather than small API calls
- **Database Operations**: Use transactions for consistency, bulk operations for performance
- **Error Handling**: Graceful degradation with detailed progress reporting

### Emerging Patterns
- **Conversational Batch Processing**: Let AI orchestrate complex multi-step operations
- **Intelligent Deduplication**: Use AI similarity rather than rule-based matching
- **Progressive Enrichment**: Start with basic data, layer on intelligence incrementally
- **Cost-Aware Processing**: Optimize for AI token efficiency and API usage

### Anti-Patterns
- **Over-Engineering**: Building complex systems before proving simple approaches
- **Premature Optimization**: Focusing on scale before validating core functionality
- **AI Microservices**: Separate services for each AI operation (integrate into data flow instead)
- **Rigid Parsing**: Rule-based extraction when AI can handle format variations

### Coding Standards
- **MCP Functions**: Clear docstrings with success criteria, comprehensive error handling
- **Async Operations**: Proper session management and resource cleanup
- **Configuration**: Environment-based config with sensible defaults
- **Testing**: Unit tests for core logic, integration tests with real APIs (limited)
- **Logging**: Structured logging with clear progress indicators

## Learning & Evolution

### What's Working Well
- **MCP Architecture**: Clean separation with powerful AI orchestration
- **recipe-scrapers Library**: Proven extraction across hundreds of sites
- **AI Processing**: Handles format variations better than expected
- **Conversational Interface**: More intuitive than traditional pipeline management

### What We're Learning
- **Token Efficiency**: Large JSON processing is more efficient than multiple small calls
- **Error Patterns**: Most failures are API rate limits or site changes, not logic errors
- **AI Capabilities**: Claude handles complex data transformation surprisingly well
- **Development Speed**: MCP servers much faster to develop than microservices

### What We've Changed
- **From**: Complex pipeline with separate AI processing service
- **To**: Integrated AI processing within database operations
- **Why**: Simpler, more efficient, better token usage

### Knowledge Gaps
- **Production Monitoring**: How to monitor MCP-based systems effectively
- **Scale Testing**: Behavior with 10,000+ recipe processing
- **Long-term Maintenance**: Update patterns for MCP servers over time

## Context for Agents

### Project Philosophy
1. **Simplicity Over Complexity**: Choose the simplest solution that works
2. **AI-First Processing**: Let AI handle intelligent decisions, use code for integration
3. **Conversational Workflows**: Natural language should orchestrate complex operations
4. **Iterative Improvement**: Start simple, add intelligence incrementally
5. **Cost Consciousness**: Optimize for development time and operational efficiency

### Default Approaches
- **Use FastMCP** for all custom MCP servers
- **Async/await patterns** for all I/O operations
- **Comprehensive error handling** with detailed logging
- **AI for intelligent processing**, code for data integration
- **Batch operations** for efficiency over real-time processing

### When to Ask Questions
- **Architectural decisions** that deviate from established patterns
- **API integration approaches** for new services
- **Database schema changes** that affect existing eKitchen functionality
- **Performance optimization** strategies for large-scale processing
- **Error handling approaches** for edge cases

### Quality Standards
- **95%+ success rates** for core processing functions
- **Comprehensive error handling** with actionable error messages
- **Clear progress reporting** for long-running operations
- **Resource cleanup** (sessions, connections, temporary data)
- **Cost efficiency** (minimize API calls, optimize token usage)

## Feature Integration Guidelines

### How Features Should Fit
- **MCP servers should be focused** on single responsibilities (discovery, processing, enrichment)
- **AI processing should be centralized** in the eKitchen Database MCP where possible
- **Cross-server communication** should flow through Claude conversations, not direct integration
- **Database operations** should maintain consistency with existing eKitchen schema

### Integration Points
- **Input**: Natural language requests through Claude Desktop
- **Processing**: MCP servers with clear, single-purpose functions
- **Storage**: Shared PostgreSQL database with transactional consistency
- **Output**: Progress reporting and results through conversation

### Cross-Feature Dependencies
- **Recipe Discovery → Database Processing**: Raw JSON handoff
- **Database Processing → Spoonacular**: Ingredient enrichment coordination
- **All MCPs → Claude**: Status reporting and error handling

## Decision Framework

### Architecture Decisions
- **When certain**: Document decision in this file with reasoning
- **When uncertain**: Prototype with simple MCP server to test approach
- **When experimental**: Create minimal viable implementation first

### Implementation Decisions
- **Follow MCP patterns** unless there's a clear reason to deviate
- **Use AI for intelligence**, not for simple data transformation
- **Ask when integrating** with existing eKitchen components

### Technical Debt
- **Acknowledge shortcuts** taken for rapid development
- **Document future improvements** without over-engineering initially
- **Learn from failures** and update patterns accordingly

## Learning Cycles

### Completed Feature Analysis
After each MCP server completion:
1. **Performance Analysis**: Did it meet success metrics?
2. **Pattern Extraction**: What approaches worked well?
3. **Integration Learnings**: How did it work with other components?
4. **User Experience**: How intuitive was the conversational interface?

### Pattern Evolution
- **Monthly review** of established patterns based on experience
- **Update anti-patterns** based on approaches that didn't work
- **Refine best practices** based on successful implementations

### Architecture Refinement
- **Quarterly assessment** of overall architecture effectiveness
- **Evolution planning** for next development phases
- **Scaling considerations** as data volumes grow

### Best Practice Updates
- **Document new patterns** discovered during implementation
- **Update quality standards** based on real-world performance
- **Refine development practices** for increased efficiency

---

## Maintenance Notes

### Regular Reviews
- **Weekly**: Update active feature status and roadmap
- **Monthly**: Review patterns, anti-patterns, and best practices
- **Quarterly**: Architecture effectiveness and evolution planning
- **After major features**: Comprehensive retrospective and learning extraction

### Agent Instructions
- **Always read this file** before starting work on any MCP server
- **Update relevant sections** when making architectural decisions or discovering new patterns
- **Ask questions** when guidance is unclear or situations don't match established patterns
- **Contribute learnings** when discovering new approaches or insights
- **Reference success metrics** when making implementation tradeoffs

**This file should evolve with the project, becoming smarter as we learn what works in practice for AI-powered recipe data ingestion.**