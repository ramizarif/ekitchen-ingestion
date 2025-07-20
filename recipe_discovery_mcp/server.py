"""Main FastMCP server for Recipe Discovery MCP

Provides conversational AI interface for recipe scraping and data collection
using the recipe-scrapers library with comprehensive error handling and
structured logging.

Enhanced with multi-site discovery engine for Issue #7.
"""

import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import structlog

from fastmcp import FastMCP
from fastmcp.tools import tool

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


class RecipeDiscoveryMCP:
    """Recipe Discovery MCP Server
    
    FastMCP server that provides tools for discovering and scraping recipes
    from multiple websites. Designed for AI orchestration through Claude Desktop
    with stdio transport.
    """
    
    def __init__(self):
        self.config = get_config()
        self.server = FastMCP("Recipe Discovery MCP")
        self.start_time = datetime.now()
        self.active_requests = 0
        self.total_requests = 0
        self.logger = structlog.get_logger().bind(component="server")
        
        # Setup logging
        setup_structured_logging()
        
        # Initialize services
        self.scraping_service = RecipeScrapingService(
            max_concurrent=self.config.max_concurrent_requests
        )
        
        # Initialize multi-site discovery components (Issue #7)
        self.http_client = AsyncHttpClient(
            timeout=self.config.request_timeout,
            max_concurrent=self.config.max_concurrent_requests
        )
        self.site_manager = SiteManager()
        self.url_manager = UrlManager(self.site_manager, self.http_client)
        self.discovery_engine = MultiSiteDiscoveryEngine(
            self.site_manager, 
            self.url_manager, 
            self.scraping_service
        )
        
        # Register MCP tools
        self._register_tools()
        
        log_server_startup(self.config)
    
    def _register_tools(self) -> None:
        """Register all MCP tools with the server"""
        # Health and diagnostics tools
        self.server.register_tool(self.health_check)
        self.server.register_tool(self.get_server_config)
        self.server.register_tool(self.get_server_metrics)
        self.server.register_tool(self.test_connectivity)
        
        # Recipe scraping tools
        self.server.register_tool(self.scrape_single_recipe)
        self.server.register_tool(self.scrape_recipe_batch)
        self.server.register_tool(self.test_scraping_service)
        self.server.register_tool(self.get_scraping_stats)
        
        # Multi-site discovery tools (Issue #7)
        self.server.register_tool(self.discover_recipes)
        self.server.register_tool(self.get_available_sites)
        self.server.register_tool(self.discover_urls_only)
        self.server.register_tool(self.test_discovery_engine)
        self.server.register_tool(self.batch_discover_recipes)
        
        self.logger.info("MCP tools registered successfully")
    
    @tool(
        name="health_check",
        description="Check MCP server health and status"
    )
    @handle_scraping_errors
    async def health_check(self) -> Dict[str, Any]:
        """Check server health and return status information
        
        Returns comprehensive health information including uptime,
        request statistics, and system status.
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "health_check")
        tracker.log_start()
        
        try:
            uptime = (datetime.now() - self.start_time).total_seconds()
            perf_logger = get_performance_logger()
            
            health = ServerHealth(
                status="healthy",
                uptime_seconds=uptime,
                active_requests=self.active_requests,
                total_requests=self.total_requests,
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
    
    @tool(
        name="get_server_config",
        description="Get current server configuration settings"
    )
    @handle_scraping_errors
    async def get_server_config(self) -> Dict[str, Any]:
        """Return current server configuration
        
        Provides visibility into server settings for debugging
        and optimization purposes.
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "get_server_config")
        tracker.log_start()
        
        try:
            config_data = {
                "server_name": self.config.server_name,
                "log_level": self.config.log_level,
                "max_concurrent_requests": self.config.max_concurrent_requests,
                "request_timeout": self.config.request_timeout,
                "requests_per_second": self.config.requests_per_second,
                "max_retries": self.config.max_retries,
                "debug_mode": self.config.is_debug(),
                "metrics_enabled": self.config.enable_metrics
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
    
    @tool(
        name="get_server_metrics",
        description="Get detailed server performance metrics"
    )
    @handle_scraping_errors
    async def get_server_metrics(self) -> Dict[str, Any]:
        """Return comprehensive server metrics
        
        Provides detailed performance statistics for monitoring
        and optimization purposes.
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "get_server_metrics")
        tracker.log_start()
        
        try:
            uptime = (datetime.now() - self.start_time).total_seconds()
            perf_logger = get_performance_logger()
            
            metrics = {
                "uptime_seconds": uptime,
                "uptime_formatted": self._format_uptime(uptime),
                "requests": {
                    "total": perf_logger.request_count,
                    "successful": perf_logger.success_count,
                    "failed": perf_logger.error_count,
                    "active": self.active_requests,
                    "success_rate_percent": perf_logger._calculate_success_rate(),
                    "requests_per_second": perf_logger._calculate_rps()
                },
                "server": {
                    "start_time": self.start_time.isoformat(),
                    "version": "0.1.0",
                    "status": "healthy"
                }
            }
            
            result = {
                "success": True,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success()
            return result
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {"operation": "get_server_metrics"})
    
    @tool(
        name="test_connectivity",
        description="Test server connectivity and basic functionality"
    )
    @handle_scraping_errors
    async def test_connectivity(self) -> Dict[str, Any]:
        """Test basic server connectivity and functionality
        
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
    
    def _format_uptime(self, uptime_seconds: float) -> str:
        """Format uptime in human-readable format"""
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        seconds = int(uptime_seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @tool(
        name="scrape_single_recipe",
        description="Scrape a single recipe from URL with comprehensive error handling"
    )
    @handle_scraping_errors
    async def scrape_single_recipe(self, url: str) -> Dict[str, Any]:
        """Scrape a single recipe from URL
        
        Args:
            url: Recipe URL to scrape
            
        Returns:
            Recipe data with scraping metadata
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "scrape_single_recipe")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            self.total_requests += 1
            
            # Validate URL
            if not url or not url.startswith(('http://', 'https://')):
                raise MCPError(f"Invalid URL provided: {url}")
            
            # Scrape the recipe
            recipe_data = await self.scraping_service.scrape_recipe(url)
            
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
            self.active_requests -= 1
    
    @tool(
        name="scrape_recipe_batch",
        description="Scrape multiple recipes in batch with progress tracking"
    )
    @handle_scraping_errors
    async def scrape_recipe_batch(
        self, 
        urls: List[str], 
        batch_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Scrape multiple recipes in batch
        
        Args:
            urls: List of recipe URLs to scrape
            batch_size: Number of recipes to process concurrently
            
        Returns:
            Batch scraping results with statistics
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "scrape_recipe_batch")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            self.total_requests += 1
            
            # Validate input
            if not urls:
                raise MCPError("No URLs provided for batch scraping")
            
            if len(urls) > 100:  # Reasonable limit
                raise MCPError(f"Too many URLs ({len(urls)}). Maximum 100 URLs per batch.")
            
            # Validate URLs
            invalid_urls = [url for url in urls if not url.startswith(('http://', 'https://'))]
            if invalid_urls:
                raise MCPError(f"Invalid URLs found: {invalid_urls[:5]}")  # Show first 5
            
            # Execute batch scraping
            start_time = time.time()
            results = await self.scraping_service.scrape_batch(urls, batch_size)
            processing_time = time.time() - start_time
            
            # Calculate statistics
            successful_count = sum(1 for r in results if r.success)
            failed_count = len(results) - successful_count
            
            # Create response
            response = ScrapingResponse(
                total_requested=len(urls),
                successful=successful_count,
                failed=failed_count,
                recipes=results,
                processing_time=processing_time
            )
            
            result = {
                "success": True,
                "batch_results": {
                    "total": response.total_requested,
                    "successful": response.successful,
                    "failed": response.failed,
                    "success_rate": f"{response.success_rate:.1f}%",
                    "processing_time": response.processing_time,
                    "recipes_per_second": len(urls) / processing_time if processing_time > 0 else 0
                },
                "recipes": [recipe.to_json() for recipe in results],
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                total_urls=len(urls),
                successful_count=successful_count,
                failed_count=failed_count,
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {
                "operation": "scrape_recipe_batch", 
                "url_count": len(urls) if urls else 0
            })
        finally:
            self.active_requests -= 1
    
    @tool(
        name="test_scraping_service",
        description="Test scraping service with known good URLs"
    )
    @handle_scraping_errors
    async def test_scraping_service(self) -> Dict[str, Any]:
        """Test scraping service with known good URLs
        
        Returns:
            Test results with service status and performance data
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "test_scraping_service")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            
            # Run the service test
            test_results = await self.scraping_service.test_scraping_service()
            
            result = {
                "success": True,
                "test_results": test_results,
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                service_status=test_results.get("service_status"),
                success_rate=test_results.get("test_summary", {}).get("success_rate")
            )
            
            return result
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {"operation": "test_scraping_service"})
        finally:
            self.active_requests -= 1
    
    @tool(
        name="get_scraping_stats",
        description="Get detailed scraping service statistics and performance metrics"
    )
    @handle_scraping_errors
    async def get_scraping_stats(self) -> Dict[str, Any]:
        """Get scraping service statistics
        
        Returns:
            Comprehensive statistics about scraping performance
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "get_scraping_stats")
        tracker.log_start()
        
        try:
            # Get service statistics
            service_stats = self.scraping_service.get_stats()
            
            result = {
                "success": True,
                "scraping_stats": service_stats,
                "server_stats": {
                    "active_requests": self.active_requests,
                    "total_requests": self.total_requests,
                    "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
                },
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success()
            return result
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {"operation": "get_scraping_stats"})
    
    # Multi-site discovery tools (Issue #7)
    
    @tool(
        name="discover_recipes",
        description="Discover and scrape recipes across multiple sites for a query"
    )
    @handle_scraping_errors
    async def discover_recipes(
        self,
        query: str,
        max_urls_per_site: int = 50,
        sites: Optional[List[str]] = None,
        validate_urls: bool = True,
        max_total_concurrent: int = 10
    ) -> Dict[str, Any]:
        """Discover recipes across multiple sites for a query
        
        Args:
            query: Search query for recipe discovery
            max_urls_per_site: Maximum URLs to discover per site
            sites: Specific site domains to search (None for all enabled)
            validate_urls: Whether to validate discovered URLs
            max_total_concurrent: Maximum concurrent operations
            
        Returns:
            Discovery results with recipes and metadata
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "discover_recipes")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            self.total_requests += 1
            
            # Create discovery configuration
            config = DiscoveryConfig(
                max_urls_per_site=max_urls_per_site,
                target_sites=sites,
                validate_urls=validate_urls,
                max_total_concurrent=max_total_concurrent
            )
            
            # Execute discovery
            start_time = time.time()
            result = await self.discovery_engine.discover_recipes(query, config)
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
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                total_recipes=len(result.recipes),
                successful_recipes=len(result.get_successful_recipes()),
                sites_processed=len(result.site_summaries),
                processing_time=processing_time
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
            self.active_requests -= 1
    
    @tool(
        name="get_available_sites",
        description="Get list of available recipe sites and their configurations"
    )
    @handle_scraping_errors
    async def get_available_sites(self) -> Dict[str, Any]:
        """Get list of available recipe sites
        
        Returns:
            Dictionary with available sites and their configurations
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "get_available_sites")
        tracker.log_start()
        
        try:
            enabled_sites = self.site_manager.get_enabled_sites()
            all_sites = self.site_manager.sites
            
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
                "site_manager_stats": self.site_manager.get_stats(),
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
    
    @tool(
        name="discover_urls_only",
        description="Discover recipe URLs without scraping content (faster for URL exploration)"
    )
    @handle_scraping_errors
    async def discover_urls_only(
        self,
        query: str,
        max_urls_per_site: int = 50,
        sites: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Discover recipe URLs without scraping content
        
        Args:
            query: Search query for URL discovery
            max_urls_per_site: Maximum URLs to discover per site
            sites: Specific site domains to search (None for all enabled)
            
        Returns:
            Dictionary with discovered URLs by site
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "discover_urls_only")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            
            start_time = time.time()
            discovered_urls = await self.url_manager.discover_recipe_urls(
                query=query,
                max_urls_per_site=max_urls_per_site,
                sites=sites
            )
            processing_time = time.time() - start_time
            
            total_urls = sum(len(urls) for urls in discovered_urls.values())
            sites_with_results = len([urls for urls in discovered_urls.values() if urls])
            
            result = {
                "success": True,
                "query": query,
                "discovered_urls": discovered_urls,
                "summary": {
                    "total_urls": total_urls,
                    "sites_searched": len(discovered_urls),
                    "sites_with_results": sites_with_results,
                    "avg_urls_per_site": total_urls / len(discovered_urls) if discovered_urls else 0,
                    "processing_time": processing_time
                },
                "url_manager_stats": self.url_manager.get_stats(),
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                total_urls=total_urls,
                sites_searched=len(discovered_urls),
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {
                "operation": "discover_urls_only",
                "query": query,
                "max_urls_per_site": max_urls_per_site
            })
        finally:
            self.active_requests -= 1
    
    @tool(
        name="test_discovery_engine",
        description="Test multi-site discovery engine with a simple query"
    )
    @handle_scraping_errors
    async def test_discovery_engine(self) -> Dict[str, Any]:
        """Test discovery engine with a simple query
        
        Returns:
            Test results with engine status and performance data
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "test_discovery_engine")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            
            test_query = "chicken recipe"
            config = DiscoveryConfig(
                max_urls_per_site=5,
                target_sites=["allrecipes.com"],
                validate_urls=False,
                max_total_concurrent=3
            )
            
            start_time = time.time()
            result = await self.discovery_engine.discover_recipes(test_query, config)
            test_time = time.time() - start_time
            
            successful_recipes = result.get_successful_recipes()
            engine_stats = self.discovery_engine.get_stats()
            
            test_report = {
                "success": True,
                "test_query": test_query,
                "test_config": {
                    "max_urls_per_site": config.max_urls_per_site,
                    "target_sites": config.target_sites,
                    "validate_urls": config.validate_urls
                },
                "test_results": {
                    "total_recipes": len(result.recipes),
                    "successful_recipes": len(successful_recipes),
                    "failed_recipes": len(result.get_failed_recipes()),
                    "success_rate": f"{len(successful_recipes)/len(result.recipes)*100:.1f}%" if result.recipes else "0%",
                    "sites_processed": len(result.site_summaries),
                    "test_duration_seconds": round(test_time, 2)
                },
                "engine_status": "operational" if successful_recipes else "degraded",
                "engine_stats": engine_stats,
                "sample_recipes": [
                    {
                        "url": recipe.url,
                        "title": recipe.title,
                        "site_domain": recipe.site_domain,
                        "ingredients_count": len(recipe.ingredients),
                        "quality_score": recipe.get_quality_score()
                    }
                    for recipe in successful_recipes[:3]  # First 3 successful recipes
                ],
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                engine_status=test_report["engine_status"],
                successful_recipes=len(successful_recipes),
                test_duration=test_time
            )
            
            return test_report
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {"operation": "test_discovery_engine"})
        finally:
            self.active_requests -= 1
    
    @tool(
        name="batch_discover_recipes",
        description="Discover recipes for multiple queries in batch"
    )
    @handle_scraping_errors
    async def batch_discover_recipes(
        self,
        queries: List[str],
        max_urls_per_site: int = 25,
        sites: Optional[List[str]] = None,
        validate_urls: bool = True,
        parallel_jobs: int = 3
    ) -> Dict[str, Any]:
        """Discover recipes for multiple queries in batch
        
        Args:
            queries: List of search queries
            max_urls_per_site: Maximum URLs to discover per site per query
            sites: Specific site domains to search (None for all enabled)
            validate_urls: Whether to validate discovered URLs
            parallel_jobs: Number of parallel discovery jobs
            
        Returns:
            Batch discovery results with statistics
        """
        tracker = create_request_tracker(str(uuid.uuid4()), "batch_discover_recipes")
        tracker.log_start()
        
        try:
            self.active_requests += 1
            
            if not queries:
                raise MCPError("No queries provided for batch discovery")
            
            if len(queries) > 20:  # Reasonable limit
                raise MCPError(f"Too many queries ({len(queries)}). Maximum 20 queries per batch.")
            
            # Create discovery configuration
            config = DiscoveryConfig(
                max_urls_per_site=max_urls_per_site,
                target_sites=sites,
                validate_urls=validate_urls,
                max_total_concurrent=min(8, parallel_jobs * 2)  # Adjust concurrency
            )
            
            # Execute batch discovery with concurrency control
            start_time = time.time()
            semaphore = asyncio.Semaphore(parallel_jobs)
            
            async def discover_single_query(query: str) -> DiscoveryResult:
                async with semaphore:
                    return await self.discovery_engine.discover_recipes(query, config)
            
            # Execute all queries concurrently
            discovery_tasks = [discover_single_query(query) for query in queries]
            results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
            
            processing_time = time.time() - start_time
            
            # Process results
            successful_results = []
            failed_results = []
            total_recipes = 0
            
            for i, result in enumerate(results):
                query = queries[i]
                if isinstance(result, Exception):
                    failed_results.append({
                        "query": query,
                        "error": str(result)
                    })
                else:
                    successful_results.append(result)
                    total_recipes += len(result.recipes)
            
            # Create batch response
            batch_response = {
                "success": True,
                "batch_summary": {
                    "total_queries": len(queries),
                    "successful_queries": len(successful_results),
                    "failed_queries": len(failed_results),
                    "success_rate": f"{len(successful_results)/len(queries)*100:.1f}%",
                    "total_recipes": total_recipes,
                    "avg_recipes_per_query": total_recipes / len(successful_results) if successful_results else 0,
                    "processing_time": processing_time
                },
                "query_results": [
                    {
                        "query": result.job.query,
                        "job_id": result.job.job_id,
                        "summary": result.summary,
                        "recipe_count": len(result.recipes),
                        "successful_recipes": len(result.get_successful_recipes())
                    }
                    for result in successful_results
                ],
                "failed_queries": failed_results,
                "aggregated_stats": {
                    "total_sites_processed": len(set(
                        site_domain 
                        for result in successful_results 
                        for site_domain in result.site_summaries.keys()
                    )),
                    "total_urls_discovered": sum(
                        result.summary.get("total_urls_discovered", 0)
                        for result in successful_results
                    )
                },
                "timestamp": datetime.now().isoformat()
            }
            
            tracker.log_success(
                total_queries=len(queries),
                successful_queries=len(successful_results),
                total_recipes=total_recipes,
                processing_time=processing_time
            )
            
            return batch_response
            
        except Exception as e:
            tracker.log_error(e)
            return create_error_response(e, {
                "operation": "batch_discover_recipes",
                "query_count": len(queries) if queries else 0
            })
        finally:
            self.active_requests -= 1
    
    async def start(self) -> None:
        """Start the MCP server with stdio transport
        
        Configures stdio transport for Claude Desktop communication
        and starts the async event loop.
        """
        try:
            self.logger.info("Starting MCP server with stdio transport")
            
            # Run the server with stdio transport
            await self.server.run_stdio()
            
        except Exception as e:
            self.logger.error(
                "Failed to start MCP server",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            raise ConfigurationError(f"Failed to start MCP server: {str(e)}")
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the MCP server
        
        Ensures proper cleanup of resources and logging of final statistics.
        """
        try:
            self.logger.info("Shutting down MCP server")
            
            # Cleanup discovery engine resources
            if hasattr(self, 'http_client'):
                await self.http_client.close()
            
            if hasattr(self, 'scraping_service'):
                await self.scraping_service.close()
            
            # Log final statistics
            if hasattr(self, 'discovery_engine'):
                engine_stats = self.discovery_engine.get_stats()
                self.logger.info(
                    "Discovery engine final statistics",
                    **engine_stats
                )
            
            log_server_shutdown()
            
        except Exception as e:
            self.logger.error(
                "Error during server shutdown",
                error_type=type(e).__name__,
                error_message=str(e)
            )


async def main() -> None:
    """Main entry point for the MCP server
    
    Creates and starts the Recipe Discovery MCP server with proper
    error handling and graceful shutdown support.
    """
    server = None
    
    try:
        server = RecipeDiscoveryMCP()
        await server.start()
        
    except KeyboardInterrupt:
        if server:
            await server.shutdown()
        print("\nServer stopped by user")
        
    except Exception as e:
        if server:
            server.logger.error(
                "Fatal server error",
                error_type=type(e).__name__,
                error_message=str(e)
            )
            await server.shutdown()
        print(f"Server failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())