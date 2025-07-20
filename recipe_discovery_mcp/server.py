"""Main FastMCP server for Recipe Discovery MCP

Provides conversational AI interface for recipe scraping and data collection
using the recipe-scrapers library with comprehensive error handling and
structured logging.

Enhanced with multi-site discovery engine for Issue #7.
"""

# Standard imports

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog

from fastmcp import FastMCP, Context

from .config import get_config
from .models import (
    RecipeData, ScrapingRequest, ScrapingResponse, ServerHealth,
    DiscoveryConfig, DiscoveryResult, BatchDiscoveryRequest, BatchDiscoveryResponse
)
from .scraper import RecipeScrapingService
from .site_manager import SiteManager
from .url_manager import UrlManager
from .discovery_engine import MultiSiteDiscoveryEngine
from .http_client import AsyncHttpClient
from .search_url_cache import SearchUrlCache
from .search_url_discoverer import SearchUrlDiscoverer
from .utils.error_handling import (
    handle_scraping_errors,
    MCPError,
    NetworkError,
    ConfigurationError,
    create_error_response
)
from .utils.logging import (
    setup_structured_logging,
    get_performance_logger,
    create_request_tracker,
    log_server_startup,
    log_server_shutdown
)


# Create the FastMCP server instance
mcp = FastMCP("Recipe Discovery MCP")

# Global state for the server
class ServerState:
    def __init__(self):
        self.config = get_config()
        self.start_time = datetime.now()
        self.active_requests = 0
        self.total_requests = 0
        self.logger = structlog.get_logger().bind(component="server")
        
        # Lazy initialization flags
        self._services_initialized = False
        self._scraping_service = None
        self._http_client = None
        self._site_manager = None
        self._url_manager = None
        self._discovery_engine = None
        self._search_url_cache = None
        self._search_url_discoverer = None
    
    def _ensure_services_initialized(self):
        """Initialize services only when first needed"""
        if self._services_initialized:
            return
            
        # Initialize services
        self._scraping_service = RecipeScrapingService(
            max_concurrent=self.config.max_concurrent_requests
        )
        
        # Initialize multi-site discovery components (Issue #7)
        self._http_client = AsyncHttpClient(
            timeout=self.config.request_timeout,
            max_concurrent=self.config.max_concurrent_requests
        )
        self._site_manager = SiteManager(http_client=self._http_client)
        self._url_manager = UrlManager(self._site_manager, self._http_client)
        
        # Initialize search URL components for enhanced discovery
        self._search_url_cache = SearchUrlCache()
        self._search_url_discoverer = SearchUrlDiscoverer(self._http_client)
        
        # Load search URL cache
        import asyncio
        try:
            asyncio.create_task(self._search_url_cache.load_cache())
        except RuntimeError:
            # Handle case where no event loop is running
            pass
        
        self._discovery_engine = MultiSiteDiscoveryEngine(
            self._site_manager, 
            self._url_manager, 
            self._scraping_service
        )
        
        self._services_initialized = True
    
    @property
    def scraping_service(self):
        self._ensure_services_initialized()
        return self._scraping_service
    
    @property
    def http_client(self):
        self._ensure_services_initialized()
        return self._http_client
    
    @property
    def site_manager(self):
        self._ensure_services_initialized()
        return self._site_manager
    
    @property
    def url_manager(self):
        self._ensure_services_initialized()
        return self._url_manager
    
    @property
    def discovery_engine(self):
        self._ensure_services_initialized()
        return self._discovery_engine
    
    @property
    def search_url_cache(self):
        self._ensure_services_initialized()
        return self._search_url_cache
    
    @property
    def search_url_discoverer(self):
        self._ensure_services_initialized()
        return self._search_url_discoverer

# Initialize server state (minimal initialization)
state = ServerState()


@mcp.tool
async def health_check() -> Dict[str, Any]:
    """Check MCP server health and status
    
    Returns comprehensive health information including uptime,
    request statistics, and system status.
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "health_check")
    tracker.log_start()
    
    try:
        uptime = (datetime.now() - state.start_time).total_seconds()
        perf_logger = get_performance_logger()
        
        health = ServerHealth(
            status="healthy",
            uptime_seconds=uptime,
            active_requests=state.active_requests,
            total_requests=state.total_requests,
            success_rate=perf_logger._calculate_success_rate()
        )
        
        result = {
            "success": True,
            "health": health.model_dump(),
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(status="healthy", uptime_seconds=uptime)
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "health_check"})


@mcp.tool
async def get_server_config() -> Dict[str, Any]:
    """Get current server configuration settings
    
    Provides visibility into server settings for debugging
    and optimization purposes.
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "get_server_config")
    tracker.log_start()
    
    try:
        config_data = {
            "server_name": state.config.server_name,
            "log_level": state.config.log_level,
            "max_concurrent_requests": state.config.max_concurrent_requests,
            "request_timeout": state.config.request_timeout,
            "requests_per_second": state.config.requests_per_second,
            "max_retries": state.config.max_retries,
            "debug_mode": state.config.is_debug(),
            "metrics_enabled": state.config.enable_metrics
        }
        
        result = {
            "success": True,
            "config": config_data,
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success()
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "get_server_config"})


@mcp.tool
async def test_connectivity() -> Dict[str, Any]:
    """Test server connectivity and basic functionality
    
    Placeholder tool for testing MCP communication with Claude Desktop.
    Will be extended with actual scraping capabilities in Issue #6.
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "test_connectivity")
    tracker.log_start()
    
    try:
        # Simulate basic async operation
        await asyncio.sleep(0.1)
        
        test_results = {
            "mcp_communication": "working",
            "async_operations": "working",
            "error_handling": "working",
            "logging": "working",
            "configuration": "loaded"
        }
        
        result = {
            "success": True,
            "test_results": test_results,
            "message": "All basic connectivity tests passed",
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success()
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "test_connectivity"})


@mcp.tool
async def scrape_single_recipe(url: str) -> Dict[str, Any]:
    """Scrape a single recipe from URL with comprehensive error handling
    
    Args:
        url: Recipe URL to scrape
        
    Returns:
        Recipe data with scraping metadata
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "scrape_single_recipe")
    tracker.log_start()
    
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Validate URL
        if not url or not url.startswith(('http://', 'https://')):
            raise MCPError(f"Invalid URL provided: {url}")
        
        # Scrape the recipe
        recipe_data = await state.scraping_service.scrape_recipe(url)
        
        result = {
            "success": True,
            "recipe": recipe_data.to_json(),
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            recipe_title=recipe_data.title,
            ingredients_count=len(recipe_data.ingredients),
            scraping_success=recipe_data.success
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "scrape_single_recipe", "url": url})
    finally:
        state.active_requests -= 1


@mcp.tool
async def discover_recipes(
    query: str,
    max_urls_per_site: int = 50,
    sites: Optional[str] = None,
    validate_urls: bool = True,
    max_total_concurrent: int = 10,
    use_smart_extraction: bool = True,
    cached_only: bool = False
) -> Dict[str, Any]:
    """Discover and scrape recipes across multiple sites for a query
    
    This is the main recipe discovery tool that orchestrates the complete workflow:
    1. Search multiple recipe sites for the query
    2. Use smart extraction to find individual recipe URLs from search pages
    3. Scrape the actual recipes for full details
    
    Args:
        query: Search query for recipe discovery
        max_urls_per_site: Maximum URLs to discover per site
        sites: Comma-separated site domains to search (e.g. "allrecipes.com,foodnetwork.com") or None for all enabled
        validate_urls: Whether to validate discovered URLs
        max_total_concurrent: Maximum concurrent operations
        use_smart_extraction: Whether to use AI-powered smart extraction for better URL discovery
        cached_only: If True, only use sites with cached search URLs (prevents hanging)
        
    Returns:
        Discovery results with recipes and metadata
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "discover_recipes")
    tracker.log_start()
    
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Parse sites parameter
        sites_list = None
        if sites:
            if sites.startswith('[') and sites.endswith(']'):
                # Handle JSON array format: ["allrecipes.com"]
                import json
                try:
                    sites_list = json.loads(sites)
                except json.JSONDecodeError:
                    sites_list = [sites.strip('[]"')]
            elif ',' in sites:
                # Handle comma-separated format: "allrecipes.com,foodnetwork.com"
                sites_list = [s.strip() for s in sites.split(',')]
            else:
                # Handle single site: "allrecipes.com"
                sites_list = [sites.strip()]
        
        # Filter to cached sites only if requested
        if cached_only:
            enabled_sites = state.site_manager.get_enabled_sites()
            cached_sites = []
            
            for site in enabled_sites:
                # Skip if specific sites requested and this isn't one of them
                if sites_list and site.domain not in sites_list:
                    continue
                    
                domain_info = await state.search_url_cache.get_domain_cache_info(site.domain)
                if domain_info and domain_info.get('cached_urls_count', 0) > 0:
                    cached_sites.append(site.domain)
            
            if not cached_sites:
                return {
                    "success": False,
                    "error": "no_cached_sites_available",
                    "message": "No sites with cached search URLs available for cached-only discovery",
                    "suggested_action": "Use populate_search_url_cache() to populate cache first",
                    "available_tools": ["get_cached_sites()", "populate_search_url_cache()"],
                    "timestamp": datetime.now().isoformat()
                }
            
            sites_list = cached_sites
            state.logger.info(f"Cached-only discovery: using {len(cached_sites)} sites with cached URLs")
        
        start_time = time.time()
        
        if use_smart_extraction:
            # Enhanced workflow with smart extraction
            result = await _discover_recipes_with_smart_extraction(
                query, max_urls_per_site, sites_list, validate_urls, max_total_concurrent, cached_only
            )
        else:
            # Original workflow
            config = DiscoveryConfig(
                max_urls_per_site=max_urls_per_site,
                target_sites=sites_list,
                validate_urls=validate_urls,
                max_total_concurrent=max_total_concurrent
            )
            result = await state.discovery_engine.discover_recipes(query, config)
        
        processing_time = time.time() - start_time
        
        # Prepare response
        response_data = {
            "success": True,
            "job_id": result.job.job_id,
            "query": query,
            "summary": result.summary,
            "recipes": [recipe.to_json() for recipe in result.recipes],
            "site_summaries": result.site_summaries,
            "url_discovery_results": {
                domain: {
                    "discovered_urls": url_result.discovered_urls,
                    "url_count": url_result.url_count,
                    "success": url_result.success
                }
                for domain, url_result in result.url_discovery_results.items()
            },
            "processing_time": processing_time,
            "smart_extraction_used": use_smart_extraction,
            "cached_only_mode": cached_only,
            "sites_used": sites_list if sites_list else "all_enabled",
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            total_recipes=len(result.recipes),
            successful_recipes=len(result.get_successful_recipes()),
            sites_processed=len(result.site_summaries),
            processing_time=processing_time,
            smart_extraction_used=use_smart_extraction
        )
        
        return response_data
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {
            "operation": "discover_recipes", 
            "query": query,
            "max_urls_per_site": max_urls_per_site
        })
    finally:
        state.active_requests -= 1


async def _discover_recipes_with_smart_extraction(
    query: str,
    max_urls_per_site: int,
    sites: Optional[List[str]],
    validate_urls: bool,
    max_total_concurrent: int,
    cached_only: bool = False
) -> DiscoveryResult:
    """Enhanced recipe discovery workflow using smart extraction
    
    This workflow:
    1. Gets search result pages from recipe sites
    2. Uses smart extraction to find actual recipe URLs
    3. Scrapes those URLs for full recipe data
    """
    from .models import DiscoveryJob, DiscoveryResult
    
    # Create job
    job = DiscoveryJob(
        job_id=str(uuid.uuid4())[:8],
        query=query,
        config=DiscoveryConfig(
            max_urls_per_site=max_urls_per_site,
            target_sites=sites,
            validate_urls=validate_urls,
            max_total_concurrent=max_total_concurrent
        ),
        started_at=datetime.now()
    )
    
    try:
        # Step 1: Get search pages from all sites
        search_pages = await _get_search_pages_for_query(query, sites, cached_only)
        
        if not search_pages:
            raise MCPError(f"No search pages found for sites: {sites}")
        
        # Step 2: Extract recipe URLs using smart extraction
        recipe_urls = []
        extraction_results = {}
        
        for site_domain, search_url in search_pages.items():
            try:
                # Use smart extraction to find recipe URLs
                extraction_result = await _smart_extract_recipe_urls_internal(
                    search_url, site_domain, max_urls_per_site
                )
                
                if extraction_result.get("success") and extraction_result.get("extracted_urls"):
                    recipe_urls.extend(extraction_result["extracted_urls"])
                    extraction_results[site_domain] = {
                        "discovered_urls": extraction_result["extracted_urls"],
                        "url_count": len(extraction_result["extracted_urls"]),
                        "success": True
                    }
                    
                    # Update cache with successful search URL usage
                    await state.search_url_cache.update_success_rate(
                        site_domain, search_url, True
                    )
                else:
                    extraction_results[site_domain] = {
                        "discovered_urls": [],
                        "url_count": 0,
                        "success": False
                    }
                    
                    # Update cache with failed search URL usage
                    await state.search_url_cache.update_success_rate(
                        site_domain, search_url, False
                    )
                    
            except Exception as e:
                extraction_results[site_domain] = {
                    "discovered_urls": [],
                    "url_count": 0,
                    "success": False,
                    "error": str(e)
                }
                
                # Update cache with failed search URL usage
                try:
                    await state.search_url_cache.update_success_rate(
                        site_domain, search_url, False
                    )
                except Exception:
                    pass  # Don't let cache errors break the main flow
        
        # Step 3: Scrape the extracted recipe URLs
        recipe_results = []
        if recipe_urls:
            # Limit to reasonable number for processing
            recipe_urls = recipe_urls[:max_urls_per_site * len(search_pages)]
            
            # Use semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_total_concurrent)
            
            async def scrape_with_limit(url):
                async with semaphore:
                    return await state.scraping_service.scrape_recipe(url)
            
            # Scrape all recipes concurrently with proper async handling
            recipe_results = await asyncio.gather(
                *[scrape_with_limit(url) for url in recipe_urls],
                return_exceptions=True
            )
            
            # Filter out exceptions
            recipe_results = [r for r in recipe_results if not isinstance(r, Exception)]
        
        # Step 4: Create result summary
        successful_recipes = [r for r in recipe_results if r.success]
        failed_recipes = [r for r in recipe_results if not r.success]
        
        # Calculate cache utilization stats
        cache_hits = 0
        discovery_attempts = 0
        for site_domain in search_pages.keys():
            cached_urls = await state.search_url_cache.get_cached_search_urls(site_domain)
            if cached_urls:
                cache_hits += 1
            else:
                discovery_attempts += 1
        
        summary = {
            "job_id": job.job_id,
            "query": query,
            "total_recipes": len(recipe_results),
            "successful_recipes": len(successful_recipes),
            "failed_recipes": len(failed_recipes),
            "success_rate": (len(successful_recipes) / len(recipe_results) * 100) if recipe_results else 0,
            "sites_processed": len(search_pages),
            "total_urls_discovered": len(recipe_urls),
            "duration_seconds": (datetime.now() - job.started_at).total_seconds(),
            "avg_recipes_per_site": len(recipe_results) / len(search_pages) if search_pages else 0,
            "smart_extraction_used": True,
            "cache_utilization": {
                "cache_hits": cache_hits,
                "discovery_attempts": discovery_attempts,
                "cache_hit_rate": (cache_hits / len(search_pages) * 100) if search_pages else 0
            }
        }
        
        # Create site summaries
        site_summaries = {}
        for site_domain in search_pages.keys():
            site_recipes = [r for r in recipe_results if r.site_domain == site_domain]
            site_successful = [r for r in site_recipes if r.success]
            
            site_summaries[site_domain] = {
                "total_urls_discovered": extraction_results.get(site_domain, {}).get("url_count", 0),
                "total_urls_validated": extraction_results.get(site_domain, {}).get("url_count", 0),
                "total_recipes_scraped": len(site_recipes),
                "successful_recipes": len(site_successful),
                "failed_recipes": len(site_recipes) - len(site_successful),
                "success_rate": (len(site_successful) / len(site_recipes) * 100) if site_recipes else 0,
                "avg_quality_score": sum(r.get_quality_score() for r in site_successful) / len(site_successful) if site_successful else 0
            }
        
        return DiscoveryResult(
            job=job,
            recipes=recipe_results,
            summary=summary,
            site_summaries=site_summaries,
            url_discovery_results=extraction_results
        )
        
    except Exception as e:
        # Return error result
        summary = {
            "job_id": job.job_id,
            "query": query,
            "total_recipes": 0,
            "successful_recipes": 0,
            "failed_recipes": 0,
            "success_rate": 0,
            "sites_processed": 0,
            "total_urls_discovered": 0,
            "duration_seconds": (datetime.now() - job.started_at).total_seconds(),
            "avg_recipes_per_site": 0,
            "smart_extraction_used": True,
            "error": str(e)
        }
        
        return DiscoveryResult(
            job=job,
            recipes=[],
            summary=summary,
            site_summaries={},
            url_discovery_results={}
        )


async def _get_search_pages_for_query(query: str, sites: Optional[List[str]], cached_only: bool = False) -> Dict[str, str]:
    """Get search result page URLs for the query from each site using cached/discovered URLs"""
    search_pages = {}
    
    # Get enabled sites
    enabled_sites = state.site_manager.get_enabled_sites()
    if sites:
        enabled_sites = [s for s in enabled_sites if s.domain in sites]
    
    for site in enabled_sites:
        try:
            # Step 1: Try to get cached search URLs first
            cached_search_urls = await state.search_url_cache.get_cached_search_urls(site.domain)
            
            if cached_search_urls:
                # Format the cached URL
                search_path = cached_search_urls[0].format(query=query)
                if not search_path.startswith('http'):
                    search_url = f"https://{site.domain}{search_path}"
                else:
                    search_url = search_path
                
                if cached_only:
                    # In cached-only mode, trust cached URLs without HTTP testing
                    search_pages[site.domain] = search_url
                    state.logger.debug(f"Using cached search URL (cached-only mode) for {site.domain}: {search_url}")
                    continue
                else:
                    # In normal mode, test the cached URL
                    try:
                        response = await state.http_client.get(search_url, timeout=10)
                        if response.status_code in [200, 301, 302]:
                            # Cached URL works, use it
                            search_pages[site.domain] = search_url
                            state.logger.debug(f"Using cached search URL for {site.domain}: {search_url}")
                            continue
                        else:
                            # Cached URL failed, remove it from cache
                            state.logger.warning(f"Cached search URL failed for {site.domain} (status {response.status_code}), removing from cache")
                            await state.search_url_cache.invalidate_domain(site.domain)
                    except Exception as e:
                        # Cached URL failed, remove it from cache
                        state.logger.warning(f"Cached search URL failed for {site.domain}: {e}, removing from cache")
                        await state.search_url_cache.invalidate_domain(site.domain)
            
            # Skip HTTP discovery and testing in cached-only mode
            if cached_only:
                if site.domain not in search_pages:
                    state.logger.info(f"Skipping {site.domain} - no cached search URLs available (cached-only mode)")
                continue
            
            # Step 2: Try configured search paths
            working_url = None
            if site.search_paths:
                for search_path in site.search_paths:
                    try:
                        formatted_path = search_path.format(query=query)
                        test_url = f"https://{site.domain}{formatted_path}"
                        
                        response = await state.http_client.get(test_url, timeout=10)
                        if response.status_code in [200, 301, 302]:
                            working_url = test_url
                            # Cache this working URL for future use
                            await state.search_url_cache.cache_search_urls(
                                site.domain, 
                                [search_path],
                                success_rate=1.0
                            )
                            state.logger.info(f"Found working configured URL for {site.domain}: {search_path}")
                            break
                    except Exception as e:
                        state.logger.debug(f"Configured path {search_path} failed for {site.domain}: {e}")
                        continue
            
            if working_url:
                search_pages[site.domain] = working_url
                continue
            
            # Step 3: If no working configured paths, try to discover new ones
            state.logger.info(f"No working configured URLs for {site.domain}, attempting discovery...")
            discovered_urls = await state.search_url_discoverer.discover_search_endpoint(site)
            
            if discovered_urls:
                # Test the discovered URLs to find one that works
                for discovered_path in discovered_urls:
                    try:
                        formatted_path = discovered_path.format(query=query)
                        if not formatted_path.startswith('http'):
                            test_url = f"https://{site.domain}{formatted_path}"
                        else:
                            test_url = formatted_path
                        
                        response = await state.http_client.get(test_url, timeout=10)
                        if response.status_code in [200, 301, 302]:
                            # Found a working discovered URL
                            await state.search_url_cache.cache_search_urls(
                                site.domain, 
                                [discovered_path],
                                success_rate=1.0
                            )
                            search_pages[site.domain] = test_url
                            state.logger.info(f"Successfully discovered and cached working URL for {site.domain}: {discovered_path}")
                            break
                    except Exception as e:
                        state.logger.debug(f"Discovered path {discovered_path} failed for {site.domain}: {e}")
                        continue
                
                if site.domain not in search_pages:
                    state.logger.warning(f"All discovered URLs failed for {site.domain}")
            else:
                state.logger.warning(
                    f"No search URLs could be discovered for {site.domain} - skipping site",
                    site_domain=site.domain,
                    query=query
                )
                
        except Exception as e:
            state.logger.error(
                f"Failed to get search URL for {site.domain}: {e}",
                site_domain=site.domain,
                error=str(e)
            )
    
    return search_pages


async def _smart_extract_recipe_urls_internal(
    search_url: str, 
    site_domain: str, 
    max_urls: int
) -> Dict[str, Any]:
    """Internal implementation of smart URL extraction"""
    try:
        # Fetch the search results page
        response = await state.http_client.get(
            search_url,
            headers={'User-Agent': 'eKitchen Recipe Discovery Bot 1.0'}
        )
        
        # Parse HTML to get links
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response, 'html.parser')
        
        # Extract links that look like recipes
        links = soup.find_all('a', href=True)
        recipe_urls = []
        
        for link in links[:200]:  # Check more links
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Simple heuristic for recipe URLs
            if href and _looks_like_recipe_url(href, text, site_domain):
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = f"https://{site_domain}{href}"
                elif not href.startswith('http'):
                    continue
                    
                if href not in recipe_urls and site_domain in href:
                    recipe_urls.append(href)
                    
                if len(recipe_urls) >= max_urls:
                    break
        
        return {
            "success": True,
            "extracted_urls": recipe_urls,
            "total_links_analyzed": len(links),
            "search_url": search_url
        }
        
    except Exception as e:
        return {
            "success": False,
            "extracted_urls": [],
            "error": str(e),
            "search_url": search_url
        }


def _looks_like_recipe_url(href: str, text: str, site_domain: str) -> bool:
    """Heuristic to determine if a URL looks like an individual recipe"""
    href_lower = href.lower()
    text_lower = text.lower()
    
    # Exclude obvious non-recipe URLs
    exclude_patterns = [
        '/recipes/collection/', '/recipes/category/', '/category/',
        '/recipes/meal-ideas/', '/recipes/ingredients/',
        '/search', '/browse', '/collections', '/topics',
        '/about', '/contact', '/privacy', '/terms',
        '/newsletter', '/subscribe', '/login', '/register'
    ]
    
    for pattern in exclude_patterns:
        if pattern in href_lower:
            return False
    
    # Include URLs that look like individual recipes
    include_patterns = [
        '/recipe/', '/recipes/', '-recipe'
    ]
    
    for pattern in include_patterns:
        if pattern in href_lower:
            # Additional check: URL should have more path segments (indicating specific recipe)
            path_segments = href.split('/')
            if len(path_segments) >= 4:  # e.g., /recipes/main-dish/pasta-carbonara
                return True
    
    # Check if text suggests it's a recipe title (longer descriptive text)
    if len(text_lower) > 15 and any(word in text_lower for word in ['recipe', 'pasta', 'chicken', 'beef', 'vegetarian', 'baked', 'grilled']):
        return True
    
    return False


@mcp.tool
async def get_available_sites() -> Dict[str, Any]:
    """Get list of available recipe sites and their configurations
    
    Returns:
        Dictionary with available sites and their configurations
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "get_available_sites")
    tracker.log_start()
    
    try:
        enabled_sites = state.site_manager.get_enabled_sites()
        all_sites = state.site_manager.sites
        
        site_info = []
        for site in enabled_sites:
            site_info.append({
                "domain": site.domain,
                "name": site.name,
                "priority": site.priority,
                "rate_limit": site.rate_limit,
                "max_concurrent": site.max_concurrent,
                "search_paths_count": len(site.search_paths),
                "recipe_patterns_count": len(site.recipe_url_patterns),
                "enabled": site.enabled
            })
        
        disabled_sites = []
        for domain, site in all_sites.items():
            if not site.enabled:
                disabled_sites.append({
                    "domain": site.domain,
                    "name": site.name,
                    "enabled": site.enabled
                })
        
        result = {
            "success": True,
            "enabled_sites": site_info,
            "disabled_sites": disabled_sites,
            "total_sites": len(all_sites),
            "enabled_count": len(enabled_sites),
            "disabled_count": len(disabled_sites),
            "site_manager_stats": state.site_manager.get_stats(),
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            enabled_sites=len(enabled_sites),
            total_sites=len(all_sites)
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "get_available_sites"})


@mcp.tool
async def get_search_url_cache_stats() -> Dict[str, Any]:
    """Get search URL cache statistics and discovered URLs
    
    Returns:
        Dictionary with cache statistics, discovered URLs per site, and success rates
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "get_search_url_cache_stats")
    tracker.log_start()
    
    try:
        # Get cache statistics
        cache_stats = await state.search_url_cache.get_cache_stats()
        
        # Get detailed information for each domain (cached and uncached)
        cached_domains = {}
        uncached_domains = {}
        enabled_sites = state.site_manager.get_enabled_sites()
        
        for site in enabled_sites:
            domain_info = await state.search_url_cache.get_domain_cache_info(site.domain)
            
            site_data = {
                "name": site.name,
                "priority": site.priority,
                "enabled": site.enabled,
                "search_paths_count": len(site.search_paths)
            }
            
            if domain_info and domain_info.get('cached_urls_count', 0) > 0:
                site_data.update(domain_info)
                cached_domains[site.domain] = site_data
            else:
                uncached_domains[site.domain] = site_data
        
        # Calculate cache readiness for recipe discovery
        cache_readiness = {
            "ready_for_cached_only_discovery": len(cached_domains) > 0,
            "sites_ready_count": len(cached_domains),
            "sites_needing_population": len(uncached_domains),
            "recommended_action": "populate_search_url_cache()" if uncached_domains else "ready_for_discovery"
        }
        
        result = {
            "success": True,
            "cache_statistics": cache_stats,
            "cached_domains": cached_domains,
            "uncached_domains": uncached_domains,
            "cache_readiness": cache_readiness,
            "coverage_metrics": {
                "total_enabled_sites": len(enabled_sites),
                "sites_with_cached_urls": len(cached_domains),
                "sites_without_cached_urls": len(uncached_domains),
                "cache_coverage_percentage": (len(cached_domains) / len(enabled_sites) * 100) if enabled_sites else 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            total_cached_domains=len(cached_domains),
            cache_coverage=result["coverage_metrics"]["cache_coverage_percentage"]
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "get_search_url_cache_stats"})


@mcp.tool
async def smart_extract_recipe_urls(
    search_url: str,
    site_domain: str,
    max_urls: int = 10
) -> Dict[str, Any]:
    """Extract recipe URLs from search results page using Claude's AI analysis
    
    Fetches a search results page and provides the HTML content to Claude for 
    intelligent extraction of individual recipe URLs, excluding category pages
    and navigation links.
    
    Args:
        search_url: URL of the search results page to analyze
        site_domain: Domain of the site (e.g., 'allrecipes.com')
        max_urls: Maximum number of recipe URLs to extract (default: 10)
        
    Returns:
        Dictionary with success status and extracted recipe URLs
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "smart_extract_recipe_urls")
    tracker.log_start()
    
    try:
        state.active_requests += 1
        state.total_requests += 1
        
        # Fetch the search results page
        response = await state.http_client.get(
            search_url,
            headers={'User-Agent': 'eKitchen Recipe Discovery Bot 1.0'}
        )
        
        # Parse HTML to get text content for Claude analysis
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response, 'html.parser')
        
        # Get all links for Claude to analyze
        links = soup.find_all('a', href=True)
        link_data = []
        
        for link in links[:100]:  # Limit to first 100 links to avoid context overflow
            href = link.get('href', '')
            text = link.get_text(strip=True)[:100]  # Limit text length
            
            # Only include links that might be recipes
            if href and ('recipe' in href.lower() or 'recipe' in text.lower() or len(text) > 10):
                link_data.append({
                    'url': href,
                    'text': text,
                    'classes': ' '.join(link.get('class', [])[:3])  # Limit classes
                })
        
        result = {
            "success": True,
            "search_url": search_url,
            "site_domain": site_domain,
            "max_urls": max_urls,
            "total_links_found": len(link_data),
            "links_for_analysis": link_data,
            "instructions": f"""
            SMART EXTRACTION TASK:
            
            Analyze the provided links from {site_domain} search results and extract {max_urls} URLs that lead to INDIVIDUAL RECIPE PAGES.
            
            CRITERIA:
            1. Must be individual recipes with ingredients/instructions (like /recipe/12345/chicken-parmesan/)
            2. Exclude category pages (like /recipes/dinner/ or /recipes/breakfast/)
            3. Exclude navigation, ads, and promotional content
            4. Only include URLs from domain: {site_domain}
            5. Convert relative URLs to absolute URLs with https://{site_domain}
            
            RETURN FORMAT:
            Return a JSON array of the recipe URLs only:
            ["https://{site_domain}/recipe/123/dish-name", "https://{site_domain}/recipe/456/other-dish"]
            
            If no individual recipe URLs found, return: []
            """,
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            search_url=search_url,
            links_found=len(link_data)
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {
            "operation": "smart_extract_recipe_urls",
            "search_url": search_url,
            "site_domain": site_domain
        })
    finally:
        state.active_requests -= 1


@mcp.tool
async def get_cached_sites() -> Dict[str, Any]:
    """Get list of sites that have verified search URLs in cache
    
    Returns only sites with cached search URLs, useful for cache-only
    recipe discovery operations.
    
    Returns:
        Dictionary with cached sites and their cache status
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "get_cached_sites")
    tracker.log_start()
    
    try:
        # Get all enabled sites
        enabled_sites = state.site_manager.get_enabled_sites()
        
        # Filter to only sites with cached URLs
        cached_sites = []
        uncached_sites = []
        
        for site in enabled_sites:
            domain_info = await state.search_url_cache.get_domain_cache_info(site.domain)
            
            site_data = {
                "domain": site.domain,
                "name": site.name,
                "priority": site.priority,
                "rate_limit": site.rate_limit,
                "max_concurrent": site.max_concurrent,
                "search_paths_count": len(site.search_paths),
                "recipe_patterns_count": len(site.recipe_url_patterns)
            }
            
            if domain_info and domain_info.get('cached_urls_count', 0) > 0:
                site_data.update({
                    "cached_urls_count": domain_info.get('cached_urls_count', 0),
                    "last_updated": domain_info.get('last_updated'),
                    "cache_age_hours": domain_info.get('cache_age_hours', 0)
                })
                cached_sites.append(site_data)
            else:
                uncached_sites.append(site_data)
        
        result = {
            "success": True,
            "cached_sites": cached_sites,
            "uncached_sites": uncached_sites,
            "total_sites": len(enabled_sites),
            "cached_sites_count": len(cached_sites),
            "cache_coverage_percentage": (len(cached_sites) / len(enabled_sites) * 100) if enabled_sites else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            cached_sites_count=len(cached_sites),
            total_sites=len(enabled_sites),
            cache_coverage=result["cache_coverage_percentage"]
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "get_cached_sites"})


@mcp.tool
async def populate_search_url_cache() -> Dict[str, Any]:
    """Workflow tool to trigger cache population for uncached sites
    
    Provides guidance on populating search URL cache using external
    Playwright MCP for browser automation. Returns list of uncached
    sites and workflow instructions.
    
    Returns:
        Dictionary with uncached sites and population workflow instructions
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "populate_search_url_cache")
    tracker.log_start()
    
    try:
        # Get sites that need cache population
        enabled_sites = state.site_manager.get_enabled_sites()
        uncached_sites = []
        
        for site in enabled_sites:
            domain_info = await state.search_url_cache.get_domain_cache_info(site.domain)
            
            if not domain_info or domain_info.get('cached_urls_count', 0) == 0:
                uncached_sites.append({
                    "domain": site.domain,
                    "name": site.name,
                    "base_url": f"https://{site.domain}",
                    "suggested_search_query": "pasta recipes",  # Generic test query
                    "search_paths": site.search_paths,
                    "priority": site.priority
                })
        
        # Sort by priority (higher priority first)
        uncached_sites.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        workflow_instructions = {
            "overview": "Use external Playwright MCP to discover search URLs for uncached sites",
            "steps": [
                {
                    "step": 1,
                    "action": "Setup Playwright MCP",
                    "description": "Ensure Microsoft Playwright MCP is configured and running",
                    "tools_needed": ["Microsoft Playwright MCP"]
                },
                {
                    "step": 2, 
                    "action": "Browser Navigation",
                    "description": "For each uncached site, navigate to base_url using Playwright",
                    "example": "Navigate to https://allrecipes.com"
                },
                {
                    "step": 3,
                    "action": "Search Form Detection", 
                    "description": "Use AI to detect search form elements and input fields",
                    "tip": "Look for search boxes, search buttons, or search icons"
                },
                {
                    "step": 4,
                    "action": "Test Search Execution",
                    "description": "Execute test search with suggested_search_query to find search URL pattern",
                    "example": "Search for 'pasta recipes' and capture resulting URL"
                },
                {
                    "step": 5,
                    "action": "URL Pattern Extraction",
                    "description": "Extract search URL pattern from browser navigation",
                    "format": "Replace query with placeholder like: https://site.com/search?q={query}"
                },
                {
                    "step": 6,
                    "action": "Cache Update",
                    "description": "Use update_search_url_cache() tool to store discovered URLs",
                    "note": "This step must be done through Recipe Discovery MCP tools"
                }
            ],
            "example_workflow": {
                "site": "allrecipes.com",
                "process": [
                    "Playwright: Navigate to https://allrecipes.com",
                    "Playwright: Find search input (typically id='search-input' or class='search-box')",
                    "Playwright: Type 'pasta recipes' and submit",
                    "Playwright: Capture resulting URL (e.g., https://allrecipes.com/search/results/?search=pasta+recipes)",
                    "Extract pattern: https://allrecipes.com/search/results/?search={query}",
                    "Recipe MCP: update_search_url_cache() with discovered pattern"
                ]
            }
        }
        
        result = {
            "success": True,
            "uncached_sites": uncached_sites,
            "uncached_sites_count": len(uncached_sites),
            "workflow_instructions": workflow_instructions,
            "next_actions": [
                "Setup external Playwright MCP server",
                "Follow workflow steps for each uncached site",
                "Use update_search_url_cache() to store discovered URLs",
                "Verify cache population with get_cached_sites()"
            ],
            "estimated_time": f"{len(uncached_sites) * 2-5} minutes per site",
            "timestamp": datetime.now().isoformat()
        }
        
        tracker.log_success(
            uncached_sites_count=len(uncached_sites),
            total_enabled_sites=len(enabled_sites)
        )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {"operation": "populate_search_url_cache"})


@mcp.tool
async def clear_search_url_cache(
    domain: Optional[str] = None,
    confirm: bool = False
) -> Dict[str, Any]:
    """Clear search URL cache for maintenance and refresh
    
    Removes cached search URLs either for specific domain or all domains.
    Requires explicit confirmation to prevent accidental data loss.
    
    Args:
        domain: Specific domain to clear (optional, clears all if not provided)
        confirm: Must be True to actually perform the clear operation
        
    Returns:
        Dictionary with cache clear results and impact summary
    """
    tracker = create_request_tracker(str(uuid.uuid4()), "clear_search_url_cache")
    tracker.log_start()
    
    try:
        if not confirm:
            # Get current cache state for preview
            cache_stats = await state.search_url_cache.get_cache_stats()
            enabled_sites = state.site_manager.get_enabled_sites()
            
            if domain:
                # Check specific domain cache
                domain_info = await state.search_url_cache.get_domain_cache_info(domain)
                sites_affected = [site for site in enabled_sites if site.domain == domain]
                
                preview_data = {
                    "operation": "clear_single_domain",
                    "domain": domain,
                    "sites_affected": len(sites_affected),
                    "cached_urls_to_remove": domain_info.get('cached_urls_count', 0) if domain_info else 0
                }
            else:
                # Preview full cache clear
                cached_domains = []
                total_cached_urls = 0
                
                for site in enabled_sites:
                    domain_info = await state.search_url_cache.get_domain_cache_info(site.domain)
                    if domain_info and domain_info.get('cached_urls_count', 0) > 0:
                        cached_domains.append({
                            "domain": site.domain,
                            "cached_urls": domain_info.get('cached_urls_count', 0)
                        })
                        total_cached_urls += domain_info.get('cached_urls_count', 0)
                
                preview_data = {
                    "operation": "clear_all_cache",
                    "domains_affected": len(cached_domains),
                    "total_cached_urls_to_remove": total_cached_urls,
                    "affected_domains": cached_domains
                }
            
            return {
                "success": True,
                "action": "preview_only",
                "message": "Cache clear operation requires explicit confirmation",
                "preview": preview_data,
                "to_confirm": {
                    "call_again_with": {
                        "domain": domain,
                        "confirm": True
                    },
                    "warning": "This operation will permanently remove cached search URLs"
                },
                "timestamp": datetime.now().isoformat()
            }
        
        # Perform actual cache clear
        if domain:
            # Clear specific domain
            cleared_urls = await state.search_url_cache.clear_domain_cache(domain)
            
            result = {
                "success": True,
                "action": "domain_cache_cleared",
                "domain": domain,
                "cleared_urls_count": cleared_urls,
                "message": f"Cache cleared for domain: {domain}",
                "next_steps": [
                    f"Use populate_search_url_cache() to repopulate {domain}",
                    "Verify cache status with get_cached_sites()"
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                domain=domain,
                cleared_urls=cleared_urls,
                operation="domain_clear"
            )
            
        else:
            # Clear all cache
            cleared_domains = await state.search_url_cache.clear_all_cache()
            
            result = {
                "success": True,
                "action": "full_cache_cleared",
                "cleared_domains_count": len(cleared_domains),
                "cleared_domains": cleared_domains,
                "message": "All cached search URLs have been cleared",
                "next_steps": [
                    "Use populate_search_url_cache() to repopulate all sites",
                    "Verify cache status with get_cached_sites()",
                    "Consider running cache population workflow"
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                cleared_domains_count=len(cleared_domains),
                operation="full_clear"
            )
        
        return result
        
    except Exception as e:
        tracker.log_error(e)
        return create_error_response(e, {
            "operation": "clear_search_url_cache",
            "domain": domain,
            "confirm": confirm
        })


async def shutdown():
    """Gracefully shutdown the MCP server
    
    Ensures proper cleanup of resources and logging of final statistics.
    """
    try:
        state.logger.info("Shutting down MCP server")
        
        # Save search URL cache before shutdown
        if hasattr(state, '_search_url_cache') and state._search_url_cache:
            await state._search_url_cache.save_cache()
        
        # Cleanup discovery engine resources
        if hasattr(state, 'http_client'):
            await state.http_client.close()
        
        if hasattr(state, 'scraping_service'):
            await state.scraping_service.close()
        
        # Log final statistics
        if hasattr(state, 'discovery_engine'):
            engine_stats = state.discovery_engine.get_stats()
            state.logger.info(
                "Discovery engine final statistics",
                **engine_stats
            )
        
        log_server_shutdown()
        
    except Exception as e:
        state.logger.error(
            "Error during server shutdown",
            error_type=type(e).__name__,
            error_message=str(e)
        )


def main():
    """Main entry point for the MCP server
    
    Creates and starts the Recipe Discovery MCP server with proper
    error handling and graceful shutdown support.
    """
    try:
        # Start the MCP server immediately
        mcp.run()
        
    except KeyboardInterrupt:
        pass
        
    except Exception as e:
        # Silent fail to avoid broken pipe issues
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()