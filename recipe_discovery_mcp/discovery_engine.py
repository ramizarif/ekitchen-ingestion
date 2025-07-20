"""Multi-Site Discovery Engine for Recipe Discovery MCP

Core engine that orchestrates recipe discovery across multiple sites
with concurrent processing, progress tracking, and error isolation.
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import structlog

from .site_manager import SiteManager  
from .url_manager import UrlManager
from .scraper import RecipeScrapingService
from .progress_tracker import ProgressTracker, DiscoveryPhase
from .models import (
    RecipeData, DiscoveryJob, DiscoveryResult, DiscoveryConfig,
    UrlDiscoveryResult, SiteConfig
)
from .utils.logging import get_logger
from .utils.error_handling import handle_scraping_errors, MCPError

logger = get_logger(__name__)


class MultiSiteDiscoveryEngine:
    """Multi-site recipe discovery engine with concurrent processing
    
    Orchestrates the complete recipe discovery workflow:
    1. URL discovery across multiple sites
    2. URL validation and filtering
    3. Concurrent recipe scraping with rate limiting
    4. Progress tracking and error isolation
    5. Result aggregation and statistics
    """
    
    def __init__(
        self,
        site_manager: SiteManager,
        url_manager: UrlManager, 
        scraping_service: RecipeScrapingService
    ):
        """Initialize discovery engine
        
        Args:
            site_manager: Site configuration manager
            url_manager: URL discovery and validation manager
            scraping_service: Recipe scraping service
        """
        self.site_manager = site_manager
        self.url_manager = url_manager  
        self.scraping_service = scraping_service
        self.logger = structlog.get_logger().bind(component="discovery_engine")
        
        # Engine statistics
        self.stats = {
            "total_discoveries": 0,
            "successful_discoveries": 0,
            "failed_discoveries": 0,
            "total_recipes_discovered": 0,
            "engine_start_time": datetime.now()
        }
        
        self.logger.info("Multi-site discovery engine initialized")
        
    @handle_scraping_errors
    async def discover_recipes(
        self, 
        query: str,
        config: DiscoveryConfig,
        progress_callback: Optional[Callable] = None
    ) -> DiscoveryResult:
        """Main entry point for multi-site recipe discovery
        
        Args:
            query: Search query for recipe discovery
            config: Discovery configuration parameters
            progress_callback: Optional callback for progress updates
            
        Returns:
            DiscoveryResult with recipes and metadata
        """
        # Create job and progress tracker
        job = DiscoveryJob(
            job_id=str(uuid.uuid4())[:8],
            query=query,
            config=config,
            started_at=datetime.now()
        )
        
        progress_tracker = ProgressTracker(
            job_id=job.job_id,
            query=query,
            progress_callback=progress_callback
        )
        
        self.stats["total_discoveries"] += 1
        
        self.logger.info(
            "Starting multi-site recipe discovery",
            job_id=job.job_id,
            query=query,
            max_urls_per_site=config.max_urls_per_site,
            target_sites=config.target_sites,
            validate_urls=config.validate_urls
        )
        
        try:
            # Phase 1: Initialize and prepare
            await progress_tracker.update_phase(DiscoveryPhase.INITIALIZING)
            target_sites = self._get_target_sites(config.target_sites)
            
            if not target_sites:
                raise MCPError("No enabled sites found for discovery")
            
            site_domains = [site.domain for site in target_sites]
            await progress_tracker.initialize_sites(site_domains)
            
            # Phase 2: URL Discovery
            await progress_tracker.update_phase(DiscoveryPhase.URL_DISCOVERY)
            discovered_urls = await self._discover_urls_phase(
                query, config, target_sites, progress_tracker
            )
            
            # Phase 3: URL Validation (optional)
            validated_urls = discovered_urls
            if config.validate_urls:
                await progress_tracker.update_phase(DiscoveryPhase.URL_VALIDATION)
                validated_urls = await self._validate_urls_phase(
                    discovered_urls, progress_tracker
                )
                
            # Phase 4: Recipe Scraping
            await progress_tracker.update_phase(DiscoveryPhase.RECIPE_SCRAPING)
            scraping_results = await self._scrape_recipes_phase(
                validated_urls, config, progress_tracker
            )
            
            # Phase 5: Result Aggregation
            await progress_tracker.update_phase(DiscoveryPhase.RESULT_AGGREGATION)
            result = await self._aggregate_results_phase(
                job, scraping_results, discovered_urls, validated_urls
            )
            
            # Complete the discovery
            await progress_tracker.mark_complete()
            self.stats["successful_discoveries"] += 1
            self.stats["total_recipes_discovered"] += len(result.recipes)
            
            self.logger.info(
                "Multi-site discovery completed successfully",
                job_id=job.job_id,
                query=query,
                total_recipes=len(result.recipes),
                successful_recipes=len(result.get_successful_recipes()),
                duration_seconds=result.summary["duration_seconds"],
                sites_processed=len(result.site_summaries)
            )
            
            return result
            
        except Exception as e:
            self.stats["failed_discoveries"] += 1
            await progress_tracker.mark_error(str(e))
            
            self.logger.error(
                "Multi-site discovery failed",
                job_id=job.job_id,
                query=query,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            # Return partial results if available
            if 'scraping_results' in locals():
                return await self._create_failed_result(job, locals().get('scraping_results', {}))
            else:
                raise
            
    async def _discover_urls_phase(
        self,
        query: str,
        config: DiscoveryConfig,
        target_sites: List[SiteConfig],
        progress_tracker: ProgressTracker
    ) -> Dict[str, List[str]]:
        """Execute URL discovery phase
        
        Args:
            query: Search query
            config: Discovery configuration
            target_sites: List of target sites
            progress_tracker: Progress tracker instance
            
        Returns:
            Dictionary mapping site domains to discovered URLs
        """
        self.logger.info(
            "Starting URL discovery phase",
            query=query,
            target_sites=[site.domain for site in target_sites]
        )
        
        discovered_urls = await self.url_manager.discover_recipe_urls(
            query=query,
            max_urls_per_site=config.max_urls_per_site,
            sites=[site.domain for site in target_sites]
        )
        
        # Update progress for each site
        for site_domain, urls in discovered_urls.items():
            await progress_tracker.update_site_progress(
                site_domain=site_domain,
                status="urls_discovered",
                completed=len(urls),
                total=len(urls),
                phase="url_discovery"
            )
            
            await progress_tracker.update_total_urls(site_domain, len(urls))
            
        total_urls = sum(len(urls) for urls in discovered_urls.values())
        self.logger.info(
            "URL discovery phase completed",
            total_urls_discovered=total_urls,
            sites_with_urls=len([d for d in discovered_urls.values() if d])
        )
        
        return discovered_urls
        
    async def _validate_urls_phase(
        self,
        discovered_urls: Dict[str, List[str]],
        progress_tracker: ProgressTracker
    ) -> Dict[str, List[str]]:
        """Execute URL validation phase
        
        Args:
            discovered_urls: URLs discovered in previous phase
            progress_tracker: Progress tracker instance
            
        Returns:
            Dictionary mapping site domains to validated URLs
        """
        self.logger.info(
            "Starting URL validation phase",
            total_urls=sum(len(urls) for urls in discovered_urls.values())
        )
        
        validated_urls = {}
        
        for site_domain, urls in discovered_urls.items():
            if not urls:
                validated_urls[site_domain] = []
                continue
                
            await progress_tracker.update_site_progress(
                site_domain=site_domain,
                status="validating_urls",
                completed=0,
                total=len(urls),
                phase="url_validation"
            )
            
            try:
                validation_results = await self.url_manager.validate_urls(urls)
                valid_urls = [url for url, is_valid in validation_results.items() if is_valid]
                validated_urls[site_domain] = valid_urls
                
                await progress_tracker.update_site_progress(
                    site_domain=site_domain,
                    status="urls_validated",
                    completed=len(valid_urls),
                    total=len(urls),
                    phase="url_validation"
                )
                
                self.logger.debug(
                    "URL validation completed for site",
                    site_domain=site_domain,
                    original_urls=len(urls),
                    valid_urls=len(valid_urls),
                    validation_rate=f"{len(valid_urls)/len(urls)*100:.1f}%"
                )
                
            except Exception as e:
                self.logger.error(
                    "URL validation failed for site",
                    site_domain=site_domain,
                    error=str(e)
                )
                validated_urls[site_domain] = urls  # Fall back to unvalidated URLs
                
                await progress_tracker.update_site_progress(
                    site_domain=site_domain,
                    status="validation_failed",
                    completed=0,
                    total=len(urls),
                    error=str(e)
                )
                
        total_validated = sum(len(urls) for urls in validated_urls.values())
        self.logger.info(
            "URL validation phase completed",
            total_validated_urls=total_validated
        )
        
        return validated_urls
        
    async def _scrape_recipes_phase(
        self,
        validated_urls: Dict[str, List[str]],
        config: DiscoveryConfig,
        progress_tracker: ProgressTracker
    ) -> Dict[str, List[RecipeData]]:
        """Execute recipe scraping phase
        
        Args:
            validated_urls: Validated URLs to scrape
            config: Discovery configuration
            progress_tracker: Progress tracker instance
            
        Returns:
            Dictionary mapping site domains to scraped recipes
        """
        total_urls = sum(len(urls) for urls in validated_urls.values())
        self.logger.info(
            "Starting recipe scraping phase",
            total_urls_to_scrape=total_urls,
            max_concurrent=config.max_total_concurrent
        )
        
        scraping_results = {}
        
        # Create global semaphore for concurrency control
        global_semaphore = asyncio.Semaphore(config.max_total_concurrent)
        
        # Create scraping tasks for each site
        scraping_tasks = []
        for site_domain, urls in validated_urls.items():
            if not urls:
                scraping_results[site_domain] = []
                continue
                
            task = self._scrape_site_recipes(
                site_domain, urls, global_semaphore, config, progress_tracker
            )
            scraping_tasks.append((site_domain, task))
            
        # Execute all scraping tasks concurrently
        results = await self._execute_scraping_tasks(scraping_tasks)
        scraping_results.update(results)
        
        total_recipes = sum(len(recipes) for recipes in scraping_results.values())
        successful_recipes = sum(
            len([r for r in recipes if r.success]) 
            for recipes in scraping_results.values()
        )
        
        self.logger.info(
            "Recipe scraping phase completed",
            total_recipes_scraped=total_recipes,
            successful_recipes=successful_recipes,
            overall_success_rate=f"{successful_recipes/total_recipes*100:.1f}%" if total_recipes > 0 else "0%"
        )
        
        return scraping_results
        
    async def _execute_scraping_tasks(
        self,
        scraping_tasks: List[tuple]
    ) -> Dict[str, List[RecipeData]]:
        """Execute scraping tasks with error isolation
        
        Args:
            scraping_tasks: List of (site_domain, task) tuples
            
        Returns:
            Dictionary of scraping results
        """
        if not scraping_tasks:
            return {}
            
        # Execute all tasks concurrently
        task_list = [task for _, task in scraping_tasks]
        results = await asyncio.gather(*task_list, return_exceptions=True)
        
        # Process results with error handling
        scraping_results = {}
        for i, result in enumerate(results):
            site_domain = scraping_tasks[i][0]
            
            if isinstance(result, Exception):
                self.logger.error(
                    "Recipe scraping failed for site",
                    site_domain=site_domain,
                    error_type=type(result).__name__,
                    error_message=str(result)
                )
                scraping_results[site_domain] = []
            else:
                scraping_results[site_domain] = result
                
        return scraping_results
        
    async def _scrape_site_recipes(
        self,
        site_domain: str,
        urls: List[str],
        global_semaphore: asyncio.Semaphore,
        config: DiscoveryConfig,
        progress_tracker: ProgressTracker
    ) -> List[RecipeData]:
        """Scrape recipes for a specific site with rate limiting
        
        Args:
            site_domain: Domain of the site
            urls: URLs to scrape
            global_semaphore: Global concurrency control
            config: Discovery configuration
            progress_tracker: Progress tracker instance
            
        Returns:
            List of scraped recipe data
        """
        site_config = self.site_manager.get_site_by_domain(site_domain)
        if not site_config:
            self.logger.error(
                "No site configuration found",
                site_domain=site_domain
            )
            return []
            
        self.logger.info(
            "Starting recipe scraping for site",
            site_domain=site_domain,
            url_count=len(urls),
            site_max_concurrent=site_config.max_concurrent,
            site_rate_limit=site_config.rate_limit
        )
        
        await progress_tracker.update_site_progress(
            site_domain=site_domain,
            status="scraping_recipes",
            completed=0,
            total=len(urls),
            phase="recipe_scraping"
        )
        
        # Create site-specific semaphore for additional rate limiting
        site_semaphore = asyncio.Semaphore(site_config.max_concurrent)
        
        async def scrape_with_limits(url: str) -> RecipeData:
            """Scrape single recipe with concurrency and rate limiting"""
            async with global_semaphore:
                async with site_semaphore:
                    # Respect site-specific rate limiting
                    if site_config.rate_limit > 0:
                        await asyncio.sleep(1.0 / site_config.rate_limit)
                    
                    try:
                        recipe_data = await self.scraping_service.scrape_recipe(url)
                        
                        # Update progress for successful scrape
                        if recipe_data.success:
                            await progress_tracker.update_recipe_success(site_domain, 1)
                            
                        return recipe_data
                        
                    except Exception as e:
                        self.logger.error(
                            "Recipe scraping error",
                            url=url,
                            site_domain=site_domain,
                            error=str(e)
                        )
                        return RecipeData.create_failed(url, str(e))
        
        # Execute scraping tasks for this site
        start_time = time.time()
        scraping_tasks = [scrape_with_limits(url) for url in urls]
        results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        processing_time = time.time() - start_time
        
        # Process results and track progress
        recipe_data = []
        successful_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Recipe scraping task failed",
                    url=urls[i] if i < len(urls) else "unknown",
                    error=str(result)
                )
                failed_recipe = RecipeData.create_failed(
                    urls[i] if i < len(urls) else "unknown",
                    f"Task execution error: {str(result)}"
                )
                recipe_data.append(failed_recipe)
            else:
                recipe_data.append(result)
                if result.success:
                    successful_count += 1
                    
        # Update final progress for this site
        await progress_tracker.update_site_progress(
            site_domain=site_domain,
            status="scraping_completed",
            completed=len(recipe_data),
            total=len(urls),
            phase="recipe_scraping"
        )
        
        self.logger.info(
            "Recipe scraping completed for site",
            site_domain=site_domain,
            total_processed=len(recipe_data),
            successful_count=successful_count,
            failed_count=len(recipe_data) - successful_count,
            success_rate=f"{successful_count/len(recipe_data)*100:.1f}%",
            processing_time=processing_time
        )
        
        return recipe_data
        
    async def _aggregate_results_phase(
        self,
        job: DiscoveryJob,
        scraping_results: Dict[str, List[RecipeData]],
        discovered_urls: Dict[str, List[str]],
        validated_urls: Dict[str, List[str]]
    ) -> DiscoveryResult:
        """Aggregate all results into final result object
        
        Args:
            job: Discovery job information
            scraping_results: Recipe scraping results
            discovered_urls: Originally discovered URLs
            validated_urls: Validated URLs
            
        Returns:
            Complete discovery result
        """
        self.logger.info("Aggregating discovery results")
        
        # Combine all recipes
        all_recipes = []
        for recipes in scraping_results.values():
            all_recipes.extend(recipes)
            
        # Create URL discovery results
        url_discovery_results = {}
        for site_domain in discovered_urls.keys():
            url_discovery_results[site_domain] = UrlDiscoveryResult(
                site_domain=site_domain,
                query=job.query,
                discovered_urls=discovered_urls.get(site_domain, []),
                search_pages_processed=1,  # Simplified for now
                processing_time=0.0,  # Would need to track this separately
                success=len(discovered_urls.get(site_domain, [])) > 0
            )
            
        # Create site summaries
        site_summaries = {}
        for site_domain, recipes in scraping_results.items():
            successful_recipes = [r for r in recipes if r.success]
            site_summaries[site_domain] = {
                "total_urls_discovered": len(discovered_urls.get(site_domain, [])),
                "total_urls_validated": len(validated_urls.get(site_domain, [])),
                "total_recipes_scraped": len(recipes),
                "successful_recipes": len(successful_recipes),
                "failed_recipes": len(recipes) - len(successful_recipes),
                "success_rate": (len(successful_recipes) / len(recipes) * 100) if recipes else 0,
                "avg_quality_score": sum(r.get_quality_score() for r in successful_recipes) / len(successful_recipes) if successful_recipes else 0
            }
            
        # Create final result
        result = DiscoveryResult(
            job=job,
            recipes=all_recipes,
            url_discovery_results=url_discovery_results,
            site_summaries=site_summaries,
            completed_at=datetime.now()
        )
        
        self.logger.info(
            "Result aggregation completed",
            total_recipes=len(all_recipes),
            successful_recipes=len(result.get_successful_recipes()),
            sites_processed=len(site_summaries)
        )
        
        return result
        
    def _get_target_sites(self, target_sites: Optional[List[str]]) -> List[SiteConfig]:
        """Get target sites for discovery
        
        Args:
            target_sites: Optional list of specific site domains
            
        Returns:
            List of target site configurations
        """
        if target_sites:
            # Use specified sites
            sites = []
            for domain in target_sites:
                site = self.site_manager.get_site_by_domain(domain)
                if site and site.enabled:
                    sites.append(site)
                else:
                    self.logger.warning(
                        "Specified site not found or disabled",
                        site_domain=domain
                    )
            return sites
        else:
            # Use all enabled sites
            return self.site_manager.get_enabled_sites()
            
    async def _create_failed_result(
        self,
        job: DiscoveryJob,
        partial_results: Dict[str, List[RecipeData]]
    ) -> DiscoveryResult:
        """Create a failed result with any partial data available
        
        Args:
            job: Discovery job information
            partial_results: Any partial scraping results
            
        Returns:
            DiscoveryResult marked as failed with partial data
        """
        all_recipes = []
        site_summaries = {}
        
        for site_domain, recipes in partial_results.items():
            all_recipes.extend(recipes)
            successful_recipes = [r for r in recipes if r.success]
            site_summaries[site_domain] = {
                "total_recipes_scraped": len(recipes),
                "successful_recipes": len(successful_recipes),
                "success_rate": (len(successful_recipes) / len(recipes) * 100) if recipes else 0,
                "status": "partial_failure"
            }
            
        return DiscoveryResult(
            job=job,
            recipes=all_recipes,
            site_summaries=site_summaries,
            completed_at=datetime.now()
        )
        
    def get_stats(self) -> Dict[str, any]:
        """Get discovery engine statistics
        
        Returns:
            Dictionary with engine performance statistics
        """
        uptime = (datetime.now() - self.stats["engine_start_time"]).total_seconds()
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "success_rate": (
                (self.stats["successful_discoveries"] / self.stats["total_discoveries"] * 100)
                if self.stats["total_discoveries"] > 0 else 100.0
            ),
            "avg_recipes_per_discovery": (
                self.stats["total_recipes_discovered"] / self.stats["successful_discoveries"]
                if self.stats["successful_discoveries"] > 0 else 0
            )
        }