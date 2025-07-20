"""URL Manager and Discovery for Recipe Discovery MCP

Handles URL discovery, validation, and extraction from recipe sites
with proper error handling and concurrency control.
"""

import asyncio
import re
import time
from typing import List, Set, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import structlog

from .site_manager import SiteManager
from .models import SiteConfig, UrlDiscoveryResult
from .http_client import AsyncHttpClient
from .utils.logging import get_logger
from .utils.error_handling import handle_scraping_errors, NetworkError, MCPError

logger = get_logger(__name__)


class UrlManager:
    """Manages URL discovery and validation for recipe sites
    
    Discovers recipe URLs from search pages across multiple sites
    with proper rate limiting, error handling, and validation.
    """
    
    def __init__(self, site_manager: SiteManager, http_client: AsyncHttpClient):
        """Initialize URL manager
        
        Args:
            site_manager: Site configuration manager
            http_client: Async HTTP client for web requests
        """
        self.site_manager = site_manager
        self.http_client = http_client
        self.discovered_urls: Set[str] = set()
        self.validated_urls: Set[str] = set()
        self.logger = structlog.get_logger().bind(component="url_manager")
        
        # Statistics tracking
        self.stats = {
            "discovery_requests": 0,
            "urls_discovered": 0,
            "urls_validated": 0,
            "validation_success_rate": 0.0,
            "last_discovery": None
        }
        
    @handle_scraping_errors
    async def discover_recipe_urls(
        self, 
        query: str, 
        max_urls_per_site: int = 50,
        sites: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """Discover recipe URLs across multiple sites for a query
        
        Args:
            query: Search query string
            max_urls_per_site: Maximum URLs to discover per site
            sites: Specific site domains to search (None for all enabled)
            
        Returns:
            Dictionary mapping site domains to lists of discovered URLs
        """
        self.stats["discovery_requests"] += 1
        self.stats["last_discovery"] = time.time()
        
        self.logger.info(
            "Starting multi-site URL discovery",
            query=query,
            max_urls_per_site=max_urls_per_site,
            target_sites=sites
        )
        
        target_sites = self._get_target_sites(sites)
        if not target_sites:
            self.logger.warning("No enabled sites found for discovery")
            return {}
        
        # Create discovery tasks for all target sites
        discovery_tasks = []
        for site in target_sites:
            if not self.site_manager.validate_site_access(site):
                self.logger.warning(
                    "Skipping invalid site configuration",
                    site_domain=site.domain
                )
                continue
                
            task = self._discover_urls_for_site(site, query, max_urls_per_site)
            discovery_tasks.append((site.domain, task))
            
        # Execute all discovery tasks concurrently
        results = await self._execute_discovery_tasks(discovery_tasks)
        
        # Log summary statistics
        total_urls = sum(len(urls) for urls in results.values())
        self.stats["urls_discovered"] += total_urls
        
        self.logger.info(
            "Multi-site URL discovery completed",
            query=query,
            sites_searched=len(results),
            total_urls_discovered=total_urls,
            avg_urls_per_site=total_urls / len(results) if results else 0
        )
        
        return results
        
    async def _execute_discovery_tasks(
        self, 
        discovery_tasks: List[Tuple[str, any]]
    ) -> Dict[str, List[str]]:
        """Execute discovery tasks with proper error handling
        
        Args:
            discovery_tasks: List of (domain, task) tuples
            
        Returns:
            Dictionary of discovery results
        """
        if not discovery_tasks:
            return {}
            
        # Execute all tasks concurrently
        task_list = [task for _, task in discovery_tasks]
        results = await asyncio.gather(*task_list, return_exceptions=True)
        
        # Process results and handle exceptions
        discovered_urls = {}
        for i, result in enumerate(results):
            domain = discovery_tasks[i][0]
            
            if isinstance(result, Exception):
                self.logger.error(
                    "URL discovery failed for site",
                    site_domain=domain,
                    error_type=type(result).__name__,
                    error_message=str(result)
                )
                discovered_urls[domain] = []
            else:
                discovered_urls[domain] = result
                
        return discovered_urls
        
    async def _discover_urls_for_site(
        self, 
        site: SiteConfig, 
        query: str, 
        max_urls: int
    ) -> List[str]:
        """Discover recipe URLs for a specific site
        
        Args:
            site: Site configuration
            query: Search query
            max_urls: Maximum URLs to discover
            
        Returns:
            List of discovered recipe URLs
        """
        self.logger.info(
            "Starting URL discovery for site",
            site_domain=site.domain,
            site_name=site.name,
            query=query,
            max_urls=max_urls
        )
        
        try:
            # Get search URLs for this site (now includes intelligent discovery)
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
            
    async def _extract_recipe_urls_from_search(
        self, 
        search_url: str, 
        site: SiteConfig,
        max_urls: int
    ) -> Set[str]:
        """Extract recipe URLs from a search results page
        
        Args:
            search_url: URL of search results page
            site: Site configuration
            max_urls: Maximum URLs to extract
            
        Returns:
            Set of discovered recipe URLs
        """
        try:
            # Respect site rate limiting
            if site.rate_limit > 0:
                await asyncio.sleep(1.0 / site.rate_limit)
            
            self.logger.debug(
                "Fetching search results page",
                search_url=search_url,
                site_domain=site.domain
            )
            
            # Fetch search results page with site-specific timeout
            response = await self.http_client.get(
                search_url, 
                timeout=site.timeout,
                headers={
                    'User-Agent': self.site_manager.get_global_setting(
                        'user_agent', 
                        'eKitchen Recipe Discovery Bot 1.0'
                    )
                }
            )
            
            # Parse HTML content
            soup = BeautifulSoup(response, 'html.parser')
            
            # Extract recipe URLs using multiple strategies
            recipe_urls = set()
            
            # Strategy 1: Look for links matching recipe URL patterns
            recipe_urls.update(
                self._extract_urls_by_patterns(soup, site, max_urls)
            )
            
            # Strategy 2: Look for JSON-LD structured data
            if len(recipe_urls) < max_urls:
                recipe_urls.update(
                    self._extract_urls_from_structured_data(soup, site, max_urls - len(recipe_urls))
                )
            
            # Strategy 3: Look for common recipe link classes/attributes
            if len(recipe_urls) < max_urls:
                recipe_urls.update(
                    self._extract_urls_by_heuristics(soup, site, max_urls - len(recipe_urls))
                )
            
            self.logger.debug(
                "Extracted recipe URLs from search page",
                search_url=search_url,
                site_domain=site.domain,
                urls_found=len(recipe_urls)
            )
            
            return recipe_urls
            
        except Exception as e:
            self.logger.error(
                "Failed to extract URLs from search page",
                search_url=search_url,
                site_domain=site.domain,
                error_type=type(e).__name__,
                error_message=str(e)
            )
            return set()
            
    def _extract_urls_by_patterns(
        self, 
        soup: BeautifulSoup, 
        site: SiteConfig, 
        max_urls: int
    ) -> Set[str]:
        """Extract URLs matching site's recipe URL patterns
        
        Args:
            soup: BeautifulSoup parsed HTML
            site: Site configuration
            max_urls: Maximum URLs to extract
            
        Returns:
            Set of matching recipe URLs
        """
        recipe_urls = set()
        
        try:
            # Find all links in the page
            for link in soup.find_all('a', href=True):
                if len(recipe_urls) >= max_urls:
                    break
                    
                href = link['href']
                
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = urljoin(site.base_url, href)
                elif not href.startswith(('http://', 'https://')):
                    # Skip non-HTTP links (mailto, javascript, etc.)
                    continue
                
                # Check if URL matches recipe patterns for this site
                if self.site_manager.is_recipe_url(href):
                    recipe_urls.add(href)
                    
        except Exception as e:
            self.logger.error(
                "Error extracting URLs by patterns",
                site_domain=site.domain,
                error=str(e)
            )
            
        return recipe_urls
        
    def _extract_urls_from_structured_data(
        self, 
        soup: BeautifulSoup, 
        site: SiteConfig, 
        max_urls: int
    ) -> Set[str]:
        """Extract recipe URLs from JSON-LD structured data
        
        Args:
            soup: BeautifulSoup parsed HTML
            site: Site configuration
            max_urls: Maximum URLs to extract
            
        Returns:
            Set of recipe URLs from structured data
        """
        recipe_urls = set()
        
        try:
            # Look for JSON-LD script tags
            for script in soup.find_all('script', type='application/ld+json'):
                if len(recipe_urls) >= max_urls:
                    break
                    
                try:
                    import json
                    data = json.loads(script.string)
                    
                    # Handle both single objects and arrays
                    if isinstance(data, list):
                        structured_items = data
                    else:
                        structured_items = [data]
                    
                    for item in structured_items:
                        if len(recipe_urls) >= max_urls:
                            break
                            
                        # Look for Recipe schema.org objects
                        if (isinstance(item, dict) and 
                            item.get('@type') == 'Recipe' and 
                            item.get('url')):
                            
                            url = item['url']
                            # Ensure absolute URL
                            if url.startswith('/'):
                                url = urljoin(site.base_url, url)
                                
                            recipe_urls.add(url)
                            
                except Exception as e:
                    self.logger.debug(
                        "Failed to parse structured data",
                        site_domain=site.domain,
                        error=str(e)
                    )
                    continue
                    
        except Exception as e:
            self.logger.error(
                "Error extracting URLs from structured data",
                site_domain=site.domain,
                error=str(e)
            )
            
        return recipe_urls
        
    def _extract_urls_by_heuristics(
        self, 
        soup: BeautifulSoup, 
        site: SiteConfig, 
        max_urls: int
    ) -> Set[str]:
        """Extract recipe URLs using common patterns and heuristics
        
        Args:
            soup: BeautifulSoup parsed HTML
            site: Site configuration
            max_urls: Maximum URLs to extract
            
        Returns:
            Set of recipe URLs found by heuristics
        """
        recipe_urls = set()
        
        try:
            # Common recipe-related CSS classes and attributes
            recipe_selectors = [
                'a[href*="recipe"]',
                'a.recipe-link',
                'a.recipe-card',
                '.recipe-title a',
                '.recipe-item a',
                '.recipe-search-result a',
                '[data-recipe-id] a',
                '.entry-title a',  # Common for WordPress recipe sites
                '.post-title a'    # Another WordPress pattern
            ]
            
            for selector in recipe_selectors:
                if len(recipe_urls) >= max_urls:
                    break
                    
                try:
                    links = soup.select(selector)
                    for link in links:
                        if len(recipe_urls) >= max_urls:
                            break
                            
                        href = link.get('href')
                        if not href:
                            continue
                            
                        # Convert to absolute URL
                        if href.startswith('/'):
                            href = urljoin(site.base_url, href)
                        elif not href.startswith(('http://', 'https://')):
                            continue
                            
                        # Additional validation that this looks like a recipe URL
                        if self._looks_like_recipe_url(href):
                            recipe_urls.add(href)
                            
                except Exception as e:
                    self.logger.debug(
                        "Error with selector",
                        selector=selector,
                        error=str(e)
                    )
                    continue
                    
        except Exception as e:
            self.logger.error(
                "Error extracting URLs by heuristics",
                site_domain=site.domain,
                error=str(e)
            )
            
        return recipe_urls
        
    def _looks_like_recipe_url(self, url: str) -> bool:
        """Heuristic check if URL looks like a recipe URL
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a recipe URL
        """
        url_lower = url.lower()
        
        # Common recipe URL indicators
        recipe_indicators = [
            'recipe', 'recipes', 'cooking', 'dish', 'meal',
            'food', 'kitchen', 'cuisine', 'ingredient'
        ]
        
        return any(indicator in url_lower for indicator in recipe_indicators)
        
    def _get_target_sites(self, sites: Optional[List[str]]) -> List[SiteConfig]:
        """Get target sites for discovery
        
        Args:
            sites: Specific site domains or None for all enabled
            
        Returns:
            List of target site configurations
        """
        if sites:
            # Use specified sites
            target_sites = []
            for site_domain in sites:
                site = self.site_manager.get_site_by_domain(site_domain)
                if site and site.enabled:
                    target_sites.append(site)
                else:
                    self.logger.warning(
                        "Site not found or disabled",
                        site_domain=site_domain
                    )
        else:
            # Use all enabled sites
            target_sites = self.site_manager.get_enabled_sites()
            
        return target_sites
        
    @handle_scraping_errors
    async def validate_urls(self, urls: List[str]) -> Dict[str, bool]:
        """Validate that URLs are accessible and contain recipes
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            Dictionary mapping URLs to validation results
        """
        if not urls:
            return {}
            
        self.logger.info(
            "Starting URL validation",
            total_urls=len(urls)
        )
        
        # Create validation tasks
        validation_tasks = []
        for url in urls:
            task = self._validate_single_url(url)
            validation_tasks.append(task)
            
        # Execute validation concurrently
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        # Process results
        validation_results = {}
        successful_validations = 0
        
        for i, result in enumerate(results):
            url = urls[i]
            if isinstance(result, Exception):
                self.logger.error(
                    "URL validation error",
                    url=url,
                    error=str(result)
                )
                validation_results[url] = False
            else:
                validation_results[url] = result
                if result:
                    successful_validations += 1
                    
        # Update statistics
        success_rate = (successful_validations / len(urls)) * 100 if urls else 0
        self.stats["urls_validated"] += len(urls)
        self.stats["validation_success_rate"] = success_rate
        
        self.logger.info(
            "URL validation completed",
            total_urls=len(urls),
            successful_validations=successful_validations,
            success_rate=f"{success_rate:.1f}%"
        )
        
        return validation_results
        
    async def _validate_single_url(self, url: str) -> bool:
        """Validate a single URL
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL appears to contain a valid recipe
        """
        try:
            # Get site configuration for rate limiting
            site = self.site_manager.get_site_for_url(url)
            if site and site.rate_limit > 0:
                await asyncio.sleep(1.0 / site.rate_limit)
            
            # Make a HEAD request first to check if URL exists
            try:
                await self.http_client.head(url, timeout=10)
            except Exception:
                # If HEAD fails, try GET with limited content
                pass
            
            # Fetch partial content to check for recipe indicators
            response = await self.http_client.get(
                url, 
                timeout=15,
                headers={'Range': 'bytes=0-4096'}  # Only get first 4KB
            )
            
            # Basic validation - check if content contains recipe indicators
            content = response.lower()
            recipe_indicators = [
                'recipe', 'ingredients', 'instructions', 
                'directions', 'cooking', 'preparation',
                'cuisine', 'serves', 'servings', 'cook time',
                'prep time', 'total time', 'calories'
            ]
            
            indicator_count = sum(1 for indicator in recipe_indicators if indicator in content)
            
            # Consider it a recipe if we find multiple indicators
            is_valid = indicator_count >= 2
            
            self.logger.debug(
                "URL validation result",
                url=url,
                indicator_count=indicator_count,
                is_valid=is_valid
            )
            
            return is_valid
            
        except Exception as e:
            self.logger.debug(
                "URL validation failed",
                url=url,
                error=str(e)
            )
            return False
            
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
        
    def _filter_by_query_relevance(self, urls: List[str], query: str) -> List[str]:
        """Filter URLs by query relevance"""
        if not query:
            return urls
            
        query_words = query.lower().split()
        scored_urls = []
        
        for url in urls:
            # Simple scoring based on query terms in URL
            url_lower = url.lower()
            score = sum(1 for word in query_words if word in url_lower)
            scored_urls.append((score, url))
            
        # Sort by relevance score (descending) and return URLs
        scored_urls.sort(key=lambda x: x[0], reverse=True)
        return [url for score, url in scored_urls]
            
    def get_stats(self) -> Dict[str, any]:
        """Get URL manager statistics
        
        Returns:
            Dictionary with URL discovery and validation statistics
        """
        return {
            **self.stats,
            "total_discovered_urls": len(self.discovered_urls),
            "total_validated_urls": len(self.validated_urls)
        }
        
    def clear_cache(self):
        """Clear internal URL caches"""
        self.discovered_urls.clear()
        self.validated_urls.clear()
        self.logger.info("URL caches cleared")