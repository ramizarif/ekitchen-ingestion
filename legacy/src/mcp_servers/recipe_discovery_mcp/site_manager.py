"""Site Manager for Recipe Discovery MCP

Manages site configurations, URL patterns, and site-specific settings
for multi-site recipe discovery operations.
"""

import json
import re
import os
import asyncio
import urllib.parse
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin
from pathlib import Path
import structlog

try:
    from recipe_scrapers import SCRAPERS
except ImportError:
    SCRAPERS = {}

from .models import SiteConfig, DiscoveryResult
from .utils.logging import get_logger
from .search_url_discoverer import SearchUrlDiscoverer
from .search_url_cache import SearchUrlCache

logger = get_logger(__name__)


class SiteManager:
    """Manages recipe site configurations and URL validation
    
    Loads site configurations from JSON files and provides utilities
    for site-specific operations like URL validation, rate limiting,
    and search URL generation.
    """
    
    def __init__(self, config_path: str = None, http_client=None):
        """Initialize site manager with configuration
        
        Args:
            config_path: Path to sites.json configuration file (deprecated - now uses recipe_scrapers)
            http_client: HTTP client for discovery operations
        """
        # Keep config_path for backward compatibility, but it's no longer used
        self.config_path = Path(config_path) if config_path else None
        self.sites: Dict[str, SiteConfig] = {}
        self.global_settings: Dict[str, any] = {}
        self.logger = structlog.get_logger().bind(component="site_manager")
        
        # Initialize search discovery and caching components
        self.http_client = http_client
        self.search_discoverer = None
        self.search_cache = SearchUrlCache()
        
        # Initialize components if http_client is available
        if self.http_client:
            self.search_discoverer = SearchUrlDiscoverer(self.http_client)
            
        self.load_site_configs()
        
        # Cache will be loaded lazily when needed to avoid event loop issues during init
        
    def load_site_configs(self):
        """Load site configurations from recipe-scrapers library"""
        try:
            # Load global settings (defaults)
            self.global_settings = {
                "max_total_concurrent": 10,
                "default_timeout": 30,
                "default_rate_limit": 2.0,
                "max_urls_per_site": 50,
                "user_agent": "eKitchen Recipe Discovery Bot 1.0"
            }
            
            # Load sites from recipe-scrapers
            if not SCRAPERS:
                self.logger.warning("recipe-scrapers not available, using fallback sites")
                self._load_default_configs()
                return
                
            # Create site configs for all recipe-scrapers supported sites
            sites_loaded = 0
            for domain in SCRAPERS.keys():
                try:
                    # Clean up domain (remove www. prefix if present)
                    clean_domain = domain.replace('www.', '') if domain.startswith('www.') else domain
                    
                    # Create a human-readable name from domain
                    name_parts = clean_domain.split('.')
                    if len(name_parts) >= 2:
                        # Take the main domain part and capitalize
                        name = name_parts[0].replace('-', ' ').replace('_', ' ').title()
                    else:
                        name = clean_domain.title()
                    
                    # Determine priority based on popularity (simplified heuristic)
                    priority = self._get_site_priority(clean_domain)
                    
                    # Create default search paths (will be discovered/cached later)
                    search_paths = [
                        "/search?q={query}",
                        "/search/?q={query}",
                        "/recipes/search?query={query}",
                        "/?s={query}"
                    ]
                    
                    # Default recipe URL patterns
                    recipe_patterns = [
                        "/recipe/.*",
                        "/recipes/.*",
                        r"/\d{4}/\d{2}/.*",  # Date-based URLs
                        r"/[^/]+/\d+/.*"      # Generic recipe URLs
                    ]
                    
                    self.sites[clean_domain] = SiteConfig(
                        domain=clean_domain,
                        name=name,
                        base_url=f"https://{clean_domain}",
                        search_paths=search_paths,
                        recipe_url_patterns=recipe_patterns,
                        priority=priority,
                        enabled=True,  # All sites enabled by default
                        rate_limit=self._get_default_rate_limit(priority),
                        max_concurrent=self._get_default_concurrent(priority)
                    )
                    sites_loaded += 1
                    
                except Exception as e:
                    self.logger.debug(
                        "Failed to create site configuration",
                        domain=domain,
                        error=str(e)
                    )
                    continue
                
            self.logger.info(
                "Site configurations loaded from recipe-scrapers",
                total_scrapers_available=len(SCRAPERS),
                sites_loaded=sites_loaded,
                enabled_sites=len(self.get_enabled_sites())
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to load site configurations from recipe-scrapers",
                error=str(e)
            )
            self._load_default_configs()
    
    def _get_site_priority(self, domain: str) -> str:
        """Determine site priority based on domain popularity"""
        # High priority sites (popular, reliable)
        high_priority = {
            'allrecipes.com', 'foodnetwork.com', 'epicurious.com', 
            'bbcgoodfood.com', 'delish.com', 'tasteofhome.com',
            'bettycrocker.com', 'pillsbury.com', 'food.com',
            'yummly.com', 'cookingchanneltv.com'
        }
        
        # Medium priority sites 
        medium_priority = {
            'simplyrecipes.com', 'foodandwine.com', 'thekitchn.com',
            'eatingwell.com', 'myrecipes.com', 'countryliving.com',
            'realsimple.com', 'southernliving.com', 'bhg.com',
            'marthastewart.com', 'bonappetit.com'
        }
        
        if domain in high_priority:
            return "high"
        elif domain in medium_priority:
            return "medium"
        else:
            return "low"
    
    def _get_default_rate_limit(self, priority: str) -> float:
        """Get default rate limit based on priority"""
        rate_limits = {
            "high": 1.0,     # 1 second between requests
            "medium": 1.5,   # 1.5 seconds between requests  
            "low": 2.0       # 2 seconds between requests
        }
        return rate_limits.get(priority, 2.0)
    
    def _get_default_concurrent(self, priority: str) -> int:
        """Get default concurrent requests based on priority"""
        concurrent_limits = {
            "high": 3,       # 3 concurrent requests
            "medium": 2,     # 2 concurrent requests
            "low": 1         # 1 concurrent request
        }
        return concurrent_limits.get(priority, 1)
            
    def _load_default_configs(self):
        """Load minimal default configurations for fallback"""
        self.logger.info("Loading default site configurations")
        
        default_sites = {
            "allrecipes.com": SiteConfig(
                domain="allrecipes.com",
                name="AllRecipes",
                base_url="https://www.allrecipes.com",
                search_paths=["/search/results/?search={query}"],
                recipe_url_patterns=["/recipe/\\d+/.*"],
                priority="high"
            ),
            "foodnetwork.com": SiteConfig(
                domain="foodnetwork.com", 
                name="Food Network",
                base_url="https://www.foodnetwork.com",
                search_paths=["/search/results?q={query}"],
                recipe_url_patterns=["/recipes/.*"],
                priority="high"
            ),
            "bbcgoodfood.com": SiteConfig(
                domain="bbcgoodfood.com",
                name="BBC Good Food",
                base_url="https://www.bbcgoodfood.com",
                search_paths=["/search/recipes?q={query}"],
                recipe_url_patterns=["/recipes/.*"],
                priority="medium"
            )
        }
        
        self.sites.update(default_sites)
        
        self.global_settings = {
            "max_total_concurrent": 10,
            "default_timeout": 30,
            "default_rate_limit": 2.0,
            "max_urls_per_site": 50,
            "user_agent": "eKitchen Recipe Discovery Bot 1.0"
        }
        
    def get_enabled_sites(self) -> List[SiteConfig]:
        """Get all enabled sites sorted by priority
        
        Returns:
            List of enabled SiteConfig objects sorted by priority
        """
        enabled = [site for site in self.sites.values() if site.enabled]
        
        # Sort by priority (high first) then by name for consistency
        priority_order = {"high": 0, "medium": 1, "low": 2}
        
        return sorted(
            enabled, 
            key=lambda x: (priority_order.get(x.priority, 3), x.name.lower())
        )
        
    def get_site_for_url(self, url: str) -> Optional[SiteConfig]:
        """Get site configuration for a given URL
        
        Args:
            url: URL to find site configuration for
            
        Returns:
            SiteConfig if found, None otherwise
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # Remove www. prefix for matching
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Try exact match first
            if domain in self.sites:
                return self.sites[domain]
            
            # Try with www. prefix
            www_domain = f"www.{domain}"
            if www_domain in self.sites:
                return self.sites[www_domain]
            
            # Try removing subdomains for broader matching
            domain_parts = domain.split('.')
            if len(domain_parts) > 2:
                base_domain = '.'.join(domain_parts[-2:])
                if base_domain in self.sites:
                    return self.sites[base_domain]
                    
            return None
            
        except Exception as e:
            self.logger.error(
                "Error extracting domain from URL",
                url=url,
                error=str(e)
            )
            return None
        
    def is_recipe_url(self, url: str) -> bool:
        """Check if URL matches recipe patterns for its site
        
        Args:
            url: URL to validate as recipe URL
            
        Returns:
            True if URL appears to be a recipe URL
        """
        site = self.get_site_for_url(url)
        if not site:
            # If no site config, this is an external domain - reject it
            return False
            
        if not site.recipe_url_patterns:
            # If no patterns defined, assume all URLs are recipe URLs
            return True
            
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            # Check if path matches any of the site's recipe URL patterns
            for pattern in site.recipe_url_patterns:
                if re.search(pattern, path):
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(
                "Error validating recipe URL pattern",
                url=url,
                site_domain=site.domain,
                error=str(e)
            )
            # Default to True on error to avoid false negatives
            return True
        
    def build_search_urls(self, site: SiteConfig, query: str) -> List[str]:
        """Build search URLs for a site and query (ORIGINAL SYNC METHOD)
        
        Args:
            site: Site configuration
            query: Search query string
            
        Returns:
            List of complete search URLs
        """
        if not site.search_paths:
            self.logger.warning(
                "No search paths configured for site",
                site_domain=site.domain
            )
            return []
            
        search_urls = []
        
        try:
            # URL-encode the query for safe inclusion in URLs
            encoded_query = urllib.parse.quote_plus(query)
            
            for path_template in site.search_paths:
                try:
                    # Replace {query} placeholder with encoded query
                    path = path_template.format(query=encoded_query)
                    full_url = urljoin(site.base_url, path)
                    search_urls.append(full_url)
                    
                except Exception as e:
                    self.logger.error(
                        "Failed to build search URL",
                        site_domain=site.domain,
                        path_template=path_template,
                        query=query,
                        error=str(e)
                    )
                    continue
                    
        except Exception as e:
            self.logger.error(
                "Error building search URLs",
                site_domain=site.domain,
                query=query,
                error=str(e)
            )
            
        self.logger.debug(
            "Built search URLs for site",
            site_domain=site.domain,
            query=query,
            url_count=len(search_urls)
        )
        
        return search_urls
        
    async def build_search_urls_enhanced(self, site: SiteConfig, query: str) -> List[str]:
        """Enhanced search URL building with intelligent discovery (NEW ASYNC METHOD)
        
        Args:
            site: Site configuration
            query: Search query string
            
        Returns:
            List of complete search URLs
        """
        
        # 1. Check cache first
        if self.search_cache:
            cached_urls = await self.search_cache.get_cached_search_urls(site.domain)
            if cached_urls:
                self.logger.debug(f"Using cached search URLs for {site.domain}")
                return self._format_search_urls(site, cached_urls, query)
            
        # 2. Use configured paths if available
        if site.search_paths:
            self.logger.debug(f"Using configured search paths for {site.domain}")
            
            # Test configured paths and cache successful ones
            valid_paths = await self._validate_search_paths(site)
            if valid_paths:
                if self.search_cache:
                    await self.search_cache.cache_search_urls(site.domain, valid_paths)
                return self._format_search_urls(site, valid_paths, query)
                
        # 3. Trigger discovery if needed
        if self.search_discoverer:
            self.logger.info(f"Discovering search URLs for {site.domain}")
            discovered_urls = await self.search_discoverer.discover_search_endpoint(site)
            
            if discovered_urls:
                if self.search_cache:
                    await self.search_cache.cache_search_urls(site.domain, discovered_urls)
                return self._format_search_urls(site, discovered_urls, query)
        
        # 4. Fallback to generic patterns
        self.logger.warning(f"Using fallback search URLs for {site.domain}")
        return self._get_fallback_search_urls(site, query)
            
    async def _validate_search_paths(self, site: SiteConfig) -> List[str]:
        """Validate configured search paths"""
        if not self.http_client:
            # If no HTTP client, assume all paths are valid
            return site.search_paths
            
        valid_paths = []
        
        for path_template in site.search_paths:
            try:
                # Extract base path without query parameters
                base_path = path_template.split('?')[0]
                test_url = urljoin(site.base_url, base_path)
                
                response = await self.http_client.head(test_url)
                if response.status_code == 200:
                    valid_paths.append(path_template)
            except Exception:
                continue
                
        return valid_paths
        
    def _format_search_urls(self, site: SiteConfig, url_templates: List[str], query: str) -> List[str]:
        """Format URL templates with query parameter and convert to absolute URLs"""
        encoded_query = urllib.parse.quote_plus(query)
        formatted_urls = []
        
        for template in url_templates:
            # Format the query placeholder
            formatted_url = template.format(query=encoded_query)
            
            # Convert relative URLs to absolute URLs
            if formatted_url.startswith('/'):
                formatted_url = urljoin(site.base_url, formatted_url)
                
            formatted_urls.append(formatted_url)
                
        return formatted_urls
        
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
        """Mark a search URL as successful and cache the URL pattern"""
        if self.search_cache:
            await self.search_cache.update_success_rate(site.domain, search_url, True)
            
            # Extract and cache the URL pattern for future use
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(search_url)
            
            # Convert the successful search URL back to a template pattern
            # e.g., https://www.allrecipes.com/search?q=chicken+recipe -> /search?q={query}
            if 'q=' in search_url:
                # Most common pattern: ?q=value
                pattern = f"{parsed.path}?q={{query}}"
            elif 'search=' in search_url:
                # Alternative pattern: ?search=value  
                pattern = f"{parsed.path}?search={{query}}"
            elif 'query=' in search_url:
                # Another pattern: ?query=value
                pattern = f"{parsed.path}?query={{query}}"
            else:
                # Fallback: just the path
                pattern = f"{parsed.path}?q={{query}}"
            
            # Cache this working pattern
            await self.search_cache.cache_search_urls(site.domain, [pattern])
            
            self.logger.info(
                "Cached successful search URL pattern",
                site_domain=site.domain,
                original_url=search_url,
                cached_pattern=pattern
            )
        
    async def mark_search_url_failed(self, site: SiteConfig, search_url: str):
        """Mark a search URL as failed"""
        if self.search_cache:
            await self.search_cache.update_success_rate(site.domain, search_url, False)
        
    def get_sites_by_priority(self, priority: str) -> List[SiteConfig]:
        """Get sites filtered by priority level
        
        Args:
            priority: Priority level ('high', 'medium', 'low')
            
        Returns:
            List of sites with specified priority
        """
        return [
            site for site in self.get_enabled_sites() 
            if site.priority == priority
        ]
        
    def get_site_by_domain(self, domain: str) -> Optional[SiteConfig]:
        """Get site configuration by domain name
        
        Args:
            domain: Domain name to search for
            
        Returns:
            SiteConfig if found, None otherwise
        """
        # Normalize domain for lookup
        domain = domain.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return self.sites.get(domain)
        
    def validate_site_access(self, site: SiteConfig) -> bool:
        """Validate that site is accessible and properly configured
        
        Args:
            site: Site configuration to validate
            
        Returns:
            True if site appears valid and accessible
        """
        if not site.enabled:
            return False
            
        if not site.base_url:
            self.logger.warning(
                "Site missing base URL",
                site_domain=site.domain
            )
            return False
            
        if not site.search_paths:
            self.logger.warning(
                "Site missing search paths",
                site_domain=site.domain
            )
            return False
            
        return True
        
    def get_global_setting(self, key: str, default=None):
        """Get global configuration setting
        
        Args:
            key: Setting key name
            default: Default value if key not found
            
        Returns:
            Setting value or default
        """
        return self.global_settings.get(key, default)
        
    def get_stats(self) -> Dict[str, any]:
        """Get site manager statistics
        
        Returns:
            Dictionary with site statistics and configuration info
        """
        enabled_sites = self.get_enabled_sites()
        
        priority_counts = {}
        for site in enabled_sites:
            priority_counts[site.priority] = priority_counts.get(site.priority, 0) + 1
            
        return {
            "total_sites": len(self.sites),
            "enabled_sites": len(enabled_sites),
            "disabled_sites": len(self.sites) - len(enabled_sites),
            "priority_distribution": priority_counts,
            "global_settings": self.global_settings,
            "source": "recipe_scrapers_library",
            "recipe_scrapers_available": len(SCRAPERS) if SCRAPERS else 0
        }