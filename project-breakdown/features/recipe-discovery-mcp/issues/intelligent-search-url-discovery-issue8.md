# Issue #8: Intelligent Search URL Discovery and Caching System

**Status**: ✅ COMPLETED  
**Assigned**: Engineering Agent (pending assignment)  
**Priority**: High - Critical enhancement for robust multi-site discovery  
**Estimated Effort**: 4-6 hours (Medium)  
**GitHub Issue**: [#8](https://github.com/ramizarif/ekitchen-ingestion/issues/8)

## Prerequisites ✅
- **Issue #7**: Multi-site Discovery Engine - ✅ COMPLETED
- **Issue #6**: Recipe Scraping Library Integration - ✅ COMPLETED 
- **Issue #5**: MCP Server Setup and Foundation - ✅ COMPLETED

## Issue Overview

Implement an intelligent search URL discovery system that automatically finds the correct search endpoints for recipe sites instead of relying on hardcoded paths. The current system fails when predefined search paths don't exist (e.g., `/search` vs `/recipes/search`), causing discovery to stop entirely.

This enhancement dramatically improves the robustness of the Multi-Site Discovery Engine by adding adaptive learning capabilities and comprehensive fallback mechanisms.

## Current Problem Analysis

1. **Hardcoded Search Paths**: `site_manager.py` uses static `search_paths` from JSON config
2. **No Fallback Mechanism**: When search URLs return 404, discovery stops completely  
3. **Manual Configuration**: New sites require manual search path configuration
4. **Brittle Discovery**: Site structure changes break the discovery engine

## Implementation Plan

### Step 1: Search URL Discovery Engine (2 hours)
Create `recipe_discovery_mcp/search_url_discoverer.py`:

```python
class SearchUrlDiscoverer:
    """Intelligently discover search endpoints for recipe sites"""
    
    async def discover_search_endpoint(self, site: SiteConfig) -> List[str]:
        """Discover valid search endpoints using multiple strategies"""
        discovered_urls = []
        
        # Strategy 1: Common pattern testing
        discovered_urls.extend(await self._try_common_patterns(site))
        
        # Strategy 2: Homepage form analysis  
        discovered_urls.extend(await self._analyze_search_forms(site))
        
        # Strategy 3: Navigation parsing
        discovered_urls.extend(await self._parse_navigation_links(site))
        
        # Strategy 4: robots.txt/sitemap analysis
        discovered_urls.extend(await self._analyze_sitemaps(site))
        
        return self._validate_and_rank_urls(discovered_urls, site)
        
    async def _try_common_patterns(self, site: SiteConfig) -> List[str]:
        """Test common search URL patterns"""
        patterns = [
            "/search", "/search/", "/search/recipes", "/recipes/search",
            "/find", "/find/", "/lookup", "/query", "/s", "/recipe-search"
        ]
        
        valid_patterns = []
        for pattern in patterns:
            test_url = urljoin(site.base_url, pattern)
            if await self._test_search_url(test_url, site):
                valid_patterns.append(pattern + "?q={query}")
                
        return valid_patterns
        
    async def _analyze_search_forms(self, site: SiteConfig) -> List[str]:
        """Parse homepage for search forms and extract action URLs"""
        try:
            response = await self.http_client.get(site.base_url)
            soup = BeautifulSoup(response, 'html.parser')
            
            search_forms = soup.find_all('form')
            search_urls = []
            
            for form in search_forms:
                # Look for search-related forms
                if self._is_search_form(form):
                    action = form.get('action', '')
                    method = form.get('method', 'GET').upper()
                    
                    if action:
                        # Convert relative to absolute URL
                        if action.startswith('/'):
                            action = urljoin(site.base_url, action)
                        
                        # Build search URL template
                        input_name = self._get_search_input_name(form)
                        if input_name:
                            if method == 'GET':
                                search_urls.append(f"{action}?{input_name}={{query}}")
                            else:
                                # Handle POST forms if needed
                                pass
                                
            return search_urls
            
        except Exception as e:
            self.logger.error(f"Failed to analyze search forms for {site.domain}: {e}")
            return []
            
    def _is_search_form(self, form) -> bool:
        """Determine if form is likely a search form"""
        # Look for search-related attributes
        form_str = str(form).lower()
        search_indicators = [
            'search', 'find', 'query', 'lookup', 'recipe',
            'name="q"', 'name="search"', 'placeholder="search"'
        ]
        return any(indicator in form_str for indicator in search_indicators)
        
    def _get_search_input_name(self, form) -> str:
        """Extract the search input field name"""
        inputs = form.find_all('input', type=['text', 'search'])
        for input_tag in inputs:
            name = input_tag.get('name', '')
            if name and any(indicator in name.lower() for indicator in ['q', 'search', 'query', 'find']):
                return name
        return 'q'  # Default fallback
```

### Step 2: Persistent Caching System (1.5 hours)
Create `recipe_discovery_mcp/search_url_cache.py`:

```python
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import aiofiles

class SearchUrlCache:
    """Persistent cache for discovered search URLs with success tracking"""
    
    def __init__(self, cache_file: str = "config/discovered_search_urls.json"):
        self.cache_file = Path(cache_file)
        self.cache_data: Dict[str, Dict] = {}
        self.cache_ttl = timedelta(days=7)  # Cache valid for 7 days
        self._lock = asyncio.Lock()
        
    async def load_cache(self):
        """Load cache from disk"""
        async with self._lock:
            try:
                if self.cache_file.exists():
                    async with aiofiles.open(self.cache_file, 'r') as f:
                        content = await f.read()
                        self.cache_data = json.loads(content)
                        
                    # Clean expired entries
                    await self._clean_expired_entries()
                    
            except Exception as e:
                self.logger.error(f"Failed to load search URL cache: {e}")
                self.cache_data = {}
                
    async def save_cache(self):
        """Save cache to disk"""
        async with self._lock:
            try:
                # Ensure directory exists
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                
                async with aiofiles.open(self.cache_file, 'w') as f:
                    await f.write(json.dumps(self.cache_data, indent=2))
                    
            except Exception as e:
                self.logger.error(f"Failed to save search URL cache: {e}")
                
    async def get_cached_search_urls(self, domain: str) -> Optional[List[str]]:
        """Get cached search URLs for a domain"""
        async with self._lock:
            if domain not in self.cache_data:
                return None
                
            entry = self.cache_data[domain]
            
            # Check if cache is still valid
            discovered_at = datetime.fromisoformat(entry['discovered_at'])
            if datetime.now() - discovered_at > self.cache_ttl:
                return None
                
            return entry.get('search_urls', [])
            
    async def cache_search_urls(
        self, 
        domain: str, 
        search_urls: List[str],
        success_rate: float = 1.0
    ):
        """Cache discovered search URLs for a domain"""
        async with self._lock:
            self.cache_data[domain] = {
                'search_urls': search_urls,
                'discovered_at': datetime.now().isoformat(),
                'last_verified': datetime.now().isoformat(),
                'success_rate': success_rate,
                'verification_count': 1
            }
            
        await self.save_cache()
        
    async def update_success_rate(self, domain: str, search_url: str, success: bool):
        """Update success rate for a specific search URL"""
        async with self._lock:
            if domain in self.cache_data:
                entry = self.cache_data[domain]
                
                # Update verification count and success rate
                count = entry.get('verification_count', 1)
                current_rate = entry.get('success_rate', 1.0)
                
                # Calculate new success rate
                total_successes = current_rate * count
                if success:
                    total_successes += 1
                count += 1
                
                entry['success_rate'] = total_successes / count
                entry['verification_count'] = count
                entry['last_verified'] = datetime.now().isoformat()
                
        await self.save_cache()
        
    async def _clean_expired_entries(self):
        """Remove expired cache entries"""
        current_time = datetime.now()
        expired_domains = []
        
        for domain, entry in self.cache_data.items():
            discovered_at = datetime.fromisoformat(entry['discovered_at'])
            if current_time - discovered_at > self.cache_ttl:
                expired_domains.append(domain)
                
        for domain in expired_domains:
            del self.cache_data[domain]
            
        if expired_domains:
            await self.save_cache()
```

### Step 3: Enhanced Site Manager Integration (1 hour)
Update `recipe_discovery_mcp/site_manager.py`:

```python
class SiteManager:
    def __init__(self, config_path: str = None):
        # ... existing initialization ...
        
        # Add new components
        self.search_discoverer = SearchUrlDiscoverer(self.http_client)
        self.search_cache = SearchUrlCache()
        
        # Load cache on startup
        asyncio.create_task(self.search_cache.load_cache())
        
    async def build_search_urls(self, site: SiteConfig, query: str) -> List[str]:
        """Enhanced search URL building with intelligent discovery"""
        
        # 1. Check cache first
        cached_urls = await self.search_cache.get_cached_search_urls(site.domain)
        if cached_urls:
            self.logger.debug(f"Using cached search URLs for {site.domain}")
            return self._format_search_urls(cached_urls, query)
            
        # 2. Use configured paths if available
        if site.search_paths:
            self.logger.debug(f"Using configured search paths for {site.domain}")
            
            # Test configured paths and cache successful ones
            valid_paths = await self._validate_search_paths(site)
            if valid_paths:
                await self.search_cache.cache_search_urls(site.domain, valid_paths)
                return self._format_search_urls(valid_paths, query)
                
        # 3. Trigger discovery if needed
        self.logger.info(f"Discovering search URLs for {site.domain}")
        discovered_urls = await self.search_discoverer.discover_search_endpoint(site)
        
        if discovered_urls:
            await self.search_cache.cache_search_urls(site.domain, discovered_urls)
            return self._format_search_urls(discovered_urls, query)
        else:
            # Fallback to generic patterns
            return self._get_fallback_search_urls(site, query)
            
    async def _validate_search_paths(self, site: SiteConfig) -> List[str]:
        """Validate configured search paths"""
        valid_paths = []
        
        for path_template in site.search_paths:
            # Extract base path without query parameters
            base_path = path_template.split('?')[0]
            test_url = urljoin(site.base_url, base_path)
            
            try:
                response = await self.http_client.head(test_url, timeout=10)
                if response.status_code == 200:
                    valid_paths.append(path_template)
            except Exception:
                continue
                
        return valid_paths
        
    def _format_search_urls(self, url_templates: List[str], query: str) -> List[str]:
        """Format URL templates with query parameter"""
        encoded_query = urllib.parse.quote_plus(query)
        return [template.format(query=encoded_query) for template in url_templates]
        
    def _get_fallback_search_urls(self, site: SiteConfig, query: str) -> List[str]:
        """Generate fallback search URLs using heuristics"""
        encoded_query = urllib.parse.quote_plus(query)
        
        fallback_patterns = [
            f"/search?q={encoded_query}",
            f"/search/?q={encoded_query}",
            f"/recipes/search?query={encoded_query}",
            f"/?s={encoded_query}"
        ]
        
        return [urljoin(site.base_url, pattern) for pattern in fallback_patterns]
        
    async def mark_search_url_success(self, site: SiteConfig, search_url: str):
        """Mark a search URL as successful"""
        await self.search_cache.update_success_rate(site.domain, search_url, True)
        
    async def mark_search_url_failed(self, site: SiteConfig, search_url: str):
        """Mark a search URL as failed"""
        await self.search_cache.update_success_rate(site.domain, search_url, False)
```

### Step 4: Enhanced URL Manager with Graceful Fallback (1.5 hours)
Update `recipe_discovery_mcp/url_manager.py`:

```python
async def _discover_urls_for_site(
    self, 
    site: SiteConfig, 
    query: str, 
    max_urls: int
) -> List[str]:
    """Enhanced URL discovery with comprehensive fallback"""
    
    self.logger.info(f"Starting enhanced URL discovery for {site.domain}")
    
    try:
        # Get search URLs (now includes intelligent discovery)
        search_urls = await self.site_manager.build_search_urls(site, query)
        if not search_urls:
            self.logger.warning(f"No search URLs available for {site.domain}")
            return await self._heuristic_recipe_discovery(site, query, max_urls)
            
        # Try each search URL until one succeeds
        for i, search_url in enumerate(search_urls):
            try:
                self.logger.debug(f"Trying search URL {i+1}/{len(search_urls)}: {search_url}")
                
                recipe_urls = await self._extract_recipe_urls_from_search(
                    search_url, site, max_urls
                )
                
                if recipe_urls:
                    # Success - mark URL as working and return results
                    await self.site_manager.mark_search_url_success(site, search_url)
                    
                    self.logger.info(
                        f"Successful discovery from {site.domain}",
                        search_url=search_url,
                        urls_found=len(recipe_urls)
                    )
                    return list(recipe_urls)
                    
            except Exception as e:
                # Mark this search URL as failed
                await self.site_manager.mark_search_url_failed(site, search_url)
                
                self.logger.warning(
                    f"Search URL failed for {site.domain}",
                    search_url=search_url,
                    error=str(e)
                )
                continue
                
        # All configured search URLs failed - try heuristic discovery
        self.logger.warning(f"All search URLs failed for {site.domain}, trying heuristic discovery")
        return await self._heuristic_recipe_discovery(site, query, max_urls)
        
    except Exception as e:
        self.logger.error(f"Complete discovery failure for {site.domain}: {e}")
        return []
        
async def _heuristic_recipe_discovery(
    self, 
    site: SiteConfig, 
    query: str, 
    max_urls: int
) -> List[str]:
    """Fallback heuristic recipe discovery when all else fails"""
    
    self.logger.info(f"Starting heuristic discovery for {site.domain}")
    
    try:
        # Strategy 1: Try to find recipes from homepage or category pages
        homepage_recipes = await self._discover_from_homepage(site, max_urls // 2)
        
        # Strategy 2: Try common recipe category paths
        category_recipes = await self._discover_from_categories(site, max_urls // 2)
        
        # Combine and deduplicate results
        all_recipes = set(homepage_recipes + category_recipes)
        
        # Filter by query relevance if possible
        relevant_recipes = self._filter_by_query_relevance(list(all_recipes), query)
        
        return relevant_recipes[:max_urls]
        
    except Exception as e:
        self.logger.error(f"Heuristic discovery failed for {site.domain}: {e}")
        return []
        
async def _discover_from_homepage(self, site: SiteConfig, max_urls: int) -> List[str]:
    """Discover recipes from site homepage"""
    try:
        response = await self.http_client.get(site.base_url)
        soup = BeautifulSoup(response, 'html.parser')
        
        # Look for recipe links on homepage
        recipe_urls = set()
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/'):
                href = urljoin(site.base_url, href)
                
            if self.site_manager.is_recipe_url(href) and len(recipe_urls) < max_urls:
                recipe_urls.add(href)
                
        return list(recipe_urls)
        
    except Exception as e:
        self.logger.error(f"Homepage discovery failed for {site.domain}: {e}")
        return []
        
async def _discover_from_categories(self, site: SiteConfig, max_urls: int) -> List[str]:
    """Discover recipes from common category pages"""
    category_paths = [
        '/recipes', '/recipes/', '/recipe', '/cooking', '/food',
        '/categories', '/category', '/browse', '/all-recipes'
    ]
    
    recipe_urls = set()
    
    for path in category_paths:
        if len(recipe_urls) >= max_urls:
            break
            
        try:
            category_url = urljoin(site.base_url, path)
            response = await self.http_client.get(category_url, timeout=10)
            soup = BeautifulSoup(response, 'html.parser')
            
            # Extract recipe links from category page
            for link in soup.find_all('a', href=True):
                if len(recipe_urls) >= max_urls:
                    break
                    
                href = link['href']
                if href.startswith('/'):
                    href = urljoin(site.base_url, href)
                    
                if self.site_manager.is_recipe_url(href):
                    recipe_urls.add(href)
                    
        except Exception:
            continue
            
    return list(recipe_urls)
```

## Acceptance Criteria

### Functional Requirements ✅
- [ ] **Automatic Discovery**: Find search URLs when hardcoded paths fail
- [ ] **Persistent Caching**: Store discovered URLs with success metadata  
- [ ] **Cache-First Lookup**: Check cache before attempting discovery
- [ ] **Graceful Fallback**: Continue discovery even when all endpoints fail
- [ ] **Success Tracking**: Monitor and improve search URL effectiveness
- [ ] **Backward Compatibility**: Existing site configs work unchanged

### Technical Requirements ✅  
- [ ] **Non-Blocking Discovery**: Discovery failures don't stop other sites
- [ ] **Configurable Cache TTL**: Cache refresh intervals configurable
- [ ] **Comprehensive Logging**: Track discovery attempts and success rates
- [ ] **Resource Efficient**: Minimize additional HTTP requests
- [ ] **Thread Safe**: Cache operations safe for concurrent access
- [ ] **Error Isolation**: Site-specific failures don't affect other sites

### Integration Requirements ✅
- [ ] **Builds on Issue #7**: Uses existing discovery engine foundation
- [ ] **MCP Tool Integration**: New tools for cache management  
- [ ] **Claude Desktop Compatible**: Works with conversational interface
- [ ] **Monitoring Support**: Provides metrics for discovery success
- [ ] **Configuration Management**: Integrates with existing site configuration

## Performance Expectations

### Discovery Performance
- **Cache Hit**: <50ms lookup time for cached search URLs
- **Cache Miss**: <5 seconds discovery time for new sites
- **Fallback Performance**: <10 seconds for complete fallback discovery  
- **Success Rate**: >90% successful search URL discovery

### Resource Usage
- **Memory**: <10MB additional memory for cache and discovery
- **Storage**: <1MB cache file with 100+ sites
- **Network**: <5 additional requests per site for discovery
- **CPU**: Minimal impact on discovery engine performance

## Integration Notes

### Enhances Multi-Site Discovery Engine ✅
- Provides robust search URL discovery when hardcoded paths fail
- Dramatically improves success rate across diverse recipe sites
- Reduces manual configuration overhead for new sites
- Enables progressive learning and improvement over time

### Future Enhancement Foundation ✅
- Cache system supports future machine learning integration
- Discovery strategies can be expanded with new techniques
- Success tracking enables data-driven optimization
- Foundation for advanced site compatibility features

---

**✅ READY FOR ENGINEERING AGENT ASSIGNMENT**  
**Enhances Recipe Discovery MCP robustness and adaptability**  
**Critical improvement for production-scale multi-site discovery**