# Issue #10: Cache-Based Search URL Discovery with External Playwright MCP Integration

**GitHub Issue**: [#10 - Add Playwright MCP for AI-led browser automation search URL discovery](https://github.com/ramizarif/ekitchen-ingestion/issues/10)  
**Feature**: Recipe Discovery MCP  
**Type**: Feature Enhancement  
**Priority**: High  
**Status**: 🔄 In Progress  
**Effort**: Medium (1 day)  
**Created**: 2025-07-20  

## Overview

Implement a cache-based search URL discovery system that integrates with external Playwright MCP for reliable search URL population. This eliminates the hanging issue by using only pre-verified cached search URLs during recipe discovery, while leveraging external browser automation for cache population.

## Problem Context

The current search URL discovery system in `recipe_discovery_mcp/search_url_discoverer.py` and `_get_search_pages_for_query()` creates excessive HTTP requests when:

1. Testing cached URLs for validity
2. Testing each configured search path 
3. Running discovery strategies (common patterns, sitemap analysis, etc.)
4. Testing each discovered URL for functionality

This cascade of HTTP requests causes the MCP server to hang when Claude tries to discover recipes, blocking the entire recipe discovery workflow.

## Solution Approach: Hybrid Cache-Population Strategy

**Key Innovation: Separate cache population from recipe discovery**

### Phase 1: Cache Population (One-time/Periodic)
1. **Recipe Discovery MCP**: `get_available_sites()` → Returns all configured sites
2. **Claude orchestrates** with external Playwright MCP to visit each site  
3. **Playwright MCP** discovers working search URLs through browser automation
4. **Recipe Discovery MCP**: `update_search_url_cache()` stores verified URLs
5. **Cache populated** with working, tested search URLs

### Phase 2: Recipe Discovery (Daily Operation)  
1. **Recipe Discovery MCP**: `discover_recipes(cached_only=True)` → Only uses cached sites
2. **Skip uncached sites** → No hanging, no HTTP discovery attempts
3. **Fast, reliable discovery** using pre-verified URLs from cache

## Technical Implementation

### Enhanced Recipe Discovery MCP Tools

1. **Cache Management Tools**
   - `get_available_sites()` - List all configured recipe sites
   - `get_cached_sites()` - List only sites with verified search URLs in cache
   - `populate_search_url_cache()` - Workflow tool to trigger cache population
   - `clear_search_url_cache()` - Cache maintenance and refresh

2. **Modified Discovery Tools**
   - `discover_recipes(cached_only=True)` - Only use sites with cached search URLs
   - `get_search_url_cache_stats()` - Enhanced with coverage metrics
   - Remove hanging-prone HTTP discovery from main workflow

3. **Integration Documentation**
   - Setup guide for external Playwright MCP
   - Cache population workflow examples
   - Troubleshooting for cache misses

### Workflow Integration

```
CACHE POPULATION WORKFLOW:
get_available_sites() → Claude + Playwright MCP → 
Browser Automation → Search URL Discovery → 
update_search_url_cache() → Verified Cache

RECIPE DISCOVERY WORKFLOW:  
discover_recipes(cached_only=True) → Check Cache → 
Use Only Cached URLs → Fast Recipe Discovery → 
No Hanging, No HTTP Discovery
```

## Acceptance Criteria

### Cache Management Tools
- [ ] `get_available_sites()` returns all configured recipe sites
- [ ] `get_cached_sites()` returns only sites with verified search URLs
- [ ] `populate_search_url_cache()` tool exists for cache population workflow
- [ ] `clear_search_url_cache()` tool exists for cache maintenance

### Modified Discovery Behavior  
- [ ] `discover_recipes(cached_only=True)` only uses cached sites
- [ ] Recipe discovery no longer hangs during URL discovery
- [ ] Sites without cached URLs are gracefully skipped
- [ ] Cache hit/miss statistics are tracked and reported

### External Integration
- [ ] Documentation for setting up Microsoft Playwright MCP
- [ ] Cache population workflow examples provided
- [ ] Integration patterns documented for Claude orchestration

## Dependencies

### Prerequisites
- Existing SearchUrlCache system (already implemented)
- Understanding of Recipe Discovery MCP tools
- External Playwright MCP setup (Microsoft implementation)

### Blocked By
- None (can start immediately)

### Blocks  
- Eliminates hanging issue blocking recipe discovery
- Enables reliable recipe discovery for cached sites only
- Foundation for systematic cache population workflows

## Implementation Plan

### Phase 1: Cache Management Tools (0.5 day)
1. Add `get_cached_sites()` tool to filter sites by cache status
2. Add `populate_search_url_cache()` workflow tool  
3. Add `clear_search_url_cache()` maintenance tool
4. Enhance `get_search_url_cache_stats()` with coverage metrics

### Phase 2: Modified Discovery Logic (0.5 day)
1. Update `discover_recipes()` with `cached_only=True` parameter
2. Modify `_get_search_pages_for_query()` to skip uncached sites
3. Remove hanging-prone HTTP discovery from main workflow
4. Add graceful skipping of sites without cached URLs

### Phase 3: Documentation and Testing (0.5 day)
1. Document external Playwright MCP setup process
2. Create cache population workflow examples  
3. Test cache-only discovery with existing cached sites
4. Validate hanging issue resolution

## Quality Considerations

### Error Handling  
- Cache misses for unavailable sites (graceful skipping)
- External Playwright MCP unavailability (fallback documentation)
- Cache corruption or inconsistency (cache rebuild tools)
- Empty cache scenarios (clear guidance for cache population)

### Performance
- Cache-only discovery eliminates hanging issues completely
- Fast site filtering based on cache status
- No HTTP requests during main discovery workflow
- Efficient cache hit/miss tracking and reporting

### Cache Management
- Persistent cache storage with TTL management
- Cache validation and refresh workflows
- Coverage metrics and monitoring
- Clear separation of cache population vs. discovery phases

## Success Metrics

1. **Reliability**: Zero hanging issues during recipe discovery  
2. **Cache Coverage**: Clear visibility into which sites have cached search URLs
3. **Performance**: Fast cache-only discovery with no HTTP request delays
4. **Workflow Separation**: Clean separation of cache population vs. recipe discovery
5. **Integration**: Smooth coordination with external Playwright MCP for cache population

## Post-Implementation

### Monitoring
- Recipe discovery success rates
- Browser automation failure patterns
- Performance metrics for discovery times
- Cache hit rates for discovered URLs

### Future Enhancements
- Support for more complex site interactions
- Advanced anti-detection techniques
- Parallel browser automation for multiple sites
- Integration with mobile site versions

---

**Engineering Agent Notes:**
- Follow existing MCP patterns from recipe discovery server
- Use structured logging for debugging browser automation
- Implement comprehensive async/await patterns
- Add proper type hints and documentation
- Test thoroughly with real recipe sites before integration