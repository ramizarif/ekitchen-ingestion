# Issue #7: Multi-site Discovery Engine Implementation

**Status**: ⏸️ Blocked (Pending Issues #5, #6 completion)  
**Assigned**: Engineering Agent (to be spawned after #6)  
**Priority**: Critical (Final core component for MVP)  
**Estimated Effort**: 8-10 hours  

## Prerequisites 
- **Issue #4**: Python Scraping Library Research - ✅ COMPLETED
- **Issue #5**: MCP Server Setup and Foundation - 🔄 IN PROGRESS
- **Issue #6**: Recipe Scraping Library Integration - ⏸️ BLOCKED

## Issue Overview

Implement parallel scraping across multiple recipe sites with configurable site lists, URL management, concurrent request handling, and real-time progress reporting for production-scale recipe discovery.

## Implementation Plan

### Step 1: Site Configuration System (60 minutes)
Create `recipe_discovery_mcp/config/sites.json` with site-specific settings:

```json
{
  "sites": {
    "allrecipes.com": {
      "name": "AllRecipes",
      "base_url": "https://www.allrecipes.com",
      "rate_limit": 1.0,
      "timeout": 30,
      "max_concurrent": 3,
      "search_paths": [
        "/search/results/?search={query}",
        "/recipes/search/?q={query}"
      ],
      "recipe_url_patterns": [
        "/recipe/\\d+/.*",
        "/recipes/.*"
      ],
      "priority": "high",
      "enabled": true
    },
    "foodnetwork.com": {
      "name": "Food Network", 
      "base_url": "https://www.foodnetwork.com",
      "rate_limit": 0.5,
      "timeout": 45,
      "max_concurrent": 2,
      "search_paths": [
        "/search/results?q={query}"
      ],
      "recipe_url_patterns": [
        "/recipes/.*"
      ],
      "priority": "high",
      "enabled": true
    },
    "epicurious.com": {
      "name": "Epicurious",
      "base_url": "https://www.epicurious.com", 
      "rate_limit": 2.0,
      "timeout": 30,
      "max_concurrent": 5,
      "search_paths": [
        "/search/{query}"
      ],
      "recipe_url_patterns": [
        "/recipes/.*"
      ],
      "priority": "medium",
      "enabled": true
    }
  },
  "global_settings": {
    "max_total_concurrent": 10,
    "default_timeout": 30,
    "default_rate_limit": 2.0,
    "max_urls_per_site": 50,
    "user_agent": "eKitchen Recipe Discovery Bot 1.0"
  }
}
```

### Step 2: Site Manager Implementation (90 minutes)
Create `recipe_discovery_mcp/site_manager.py`:

```python
import json
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin
from pathlib import Path

from .models import SiteConfig, DiscoveryResult
from .utils.logging import get_logger

logger = get_logger(__name__)

class SiteManager:
    def __init__(self, config_path: str = "config/sites.json"):
        self.config_path = Path(config_path)
        self.sites: Dict[str, SiteConfig] = {}
        self.load_site_configs()
        
    def load_site_configs(self):
        """Load site configurations from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
                
            for domain, site_data in config_data["sites"].items():
                self.sites[domain] = SiteConfig(
                    domain=domain,
                    **site_data
                )
                
            logger.info(f"Loaded {len(self.sites)} site configurations")
            
        except Exception as e:
            logger.error(f"Failed to load site configs: {e}")
            self._load_default_configs()
            
    def _load_default_configs(self):
        """Load minimal default configurations"""
        default_sites = {
            "allrecipes.com": SiteConfig(
                domain="allrecipes.com",
                name="AllRecipes",
                base_url="https://www.allrecipes.com"
            ),
            "foodnetwork.com": SiteConfig(
                domain="foodnetwork.com", 
                name="Food Network",
                base_url="https://www.foodnetwork.com"
            )
        }
        self.sites.update(default_sites)
        
    def get_enabled_sites(self) -> List[SiteConfig]:
        """Get all enabled sites sorted by priority"""
        enabled = [site for site in self.sites.values() if site.enabled]
        return sorted(enabled, key=lambda x: (x.priority == "high", x.name))
        
    def get_site_for_url(self, url: str) -> Optional[SiteConfig]:
        """Get site configuration for a given URL"""
        domain = urlparse(url).netloc
        return self.sites.get(domain)
        
    def is_recipe_url(self, url: str) -> bool:
        """Check if URL matches recipe patterns for its site"""
        site = self.get_site_for_url(url)
        if not site or not site.recipe_url_patterns:
            return True  # Default to assume recipe URL
            
        path = urlparse(url).path
        return any(re.match(pattern, path) for pattern in site.recipe_url_patterns)
        
    def build_search_urls(self, site: SiteConfig, query: str) -> List[str]:
        """Build search URLs for a site and query"""
        if not site.search_paths:
            return []
            
        search_urls = []
        for path_template in site.search_paths:
            path = path_template.format(query=query)
            full_url = urljoin(site.base_url, path)
            search_urls.append(full_url)
            
        return search_urls
```

### Step 3: URL Manager and Discovery (105 minutes)
Create `recipe_discovery_mcp/url_manager.py`:

```python
import asyncio
import re
from typing import List, Set, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import httpx

from .site_manager import SiteManager
from .models import SiteConfig, UrlDiscoveryResult
from .http_client import AsyncHttpClient
from .utils.logging import get_logger

logger = get_logger(__name__)

class UrlManager:
    def __init__(self, site_manager: SiteManager, http_client: AsyncHttpClient):
        self.site_manager = site_manager
        self.http_client = http_client
        self.discovered_urls: Set[str] = set()
        self.validated_urls: Set[str] = set()
        
    async def discover_recipe_urls(
        self, 
        query: str, 
        max_urls_per_site: int = 50,
        sites: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """Discover recipe URLs across multiple sites for a query"""
        
        target_sites = self._get_target_sites(sites)
        discovery_tasks = []
        
        for site in target_sites:
            task = self._discover_urls_for_site(site, query, max_urls_per_site)
            discovery_tasks.append(task)
            
        results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
        
        # Aggregate results
        discovered_urls = {}
        for i, result in enumerate(results):
            site = target_sites[i]
            if isinstance(result, Exception):
                logger.error(f"URL discovery failed for {site.domain}: {result}")
                discovered_urls[site.domain] = []
            else:
                discovered_urls[site.domain] = result
                
        return discovered_urls
        
    async def _discover_urls_for_site(
        self, 
        site: SiteConfig, 
        query: str, 
        max_urls: int
    ) -> List[str]:
        """Discover recipe URLs for a specific site"""
        
        logger.info(f"Discovering URLs for {site.name} with query: {query}")
        
        try:
            # Get search URLs for this site
            search_urls = self.site_manager.build_search_urls(site, query)
            if not search_urls:
                logger.warning(f"No search paths configured for {site.domain}")
                return []
                
            # Search each search URL
            all_recipe_urls = set()
            for search_url in search_urls:
                recipe_urls = await self._extract_recipe_urls_from_search(
                    search_url, site, max_urls
                )
                all_recipe_urls.update(recipe_urls)
                
                if len(all_recipe_urls) >= max_urls:
                    break
                    
            # Limit to max_urls and return as list
            return list(all_recipe_urls)[:max_urls]
            
        except Exception as e:
            logger.error(f"Failed to discover URLs for {site.domain}: {e}")
            return []
            
    async def _extract_recipe_urls_from_search(
        self, 
        search_url: str, 
        site: SiteConfig,
        max_urls: int
    ) -> Set[str]:
        """Extract recipe URLs from a search results page"""
        
        try:
            # Respect rate limiting for this site
            await asyncio.sleep(1.0 / site.rate_limit)
            
            # Fetch search results page
            response = await self.http_client.get(search_url)
            soup = BeautifulSoup(response, 'html.parser')
            
            # Extract recipe URLs using multiple strategies
            recipe_urls = set()
            
            # Strategy 1: Look for links matching recipe URL patterns
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.startswith('/'):
                    href = urljoin(site.base_url, href)
                    
                if self.site_manager.is_recipe_url(href):
                    recipe_urls.add(href)
                    
                if len(recipe_urls) >= max_urls:
                    break
                    
            # Strategy 2: Look for JSON-LD recipe data
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        data = data[0]
                    if data.get('@type') == 'Recipe' and data.get('url'):
                        recipe_urls.add(data['url'])
                except:
                    continue
                    
            logger.info(f"Found {len(recipe_urls)} recipe URLs from {search_url}")
            return recipe_urls
            
        except Exception as e:
            logger.error(f"Failed to extract URLs from {search_url}: {e}")
            return set()
            
    def _get_target_sites(self, sites: Optional[List[str]]) -> List[SiteConfig]:
        """Get target sites for discovery"""
        if sites:
            # Use specified sites
            target_sites = []
            for site_domain in sites:
                site = self.site_manager.sites.get(site_domain)
                if site and site.enabled:
                    target_sites.append(site)
                else:
                    logger.warning(f"Site {site_domain} not found or disabled")
        else:
            # Use all enabled sites
            target_sites = self.site_manager.get_enabled_sites()
            
        return target_sites
        
    async def validate_urls(self, urls: List[str]) -> Dict[str, bool]:
        """Validate that URLs are accessible and contain recipes"""
        validation_tasks = []
        for url in urls:
            task = self._validate_single_url(url)
            validation_tasks.append(task)
            
        results = await asyncio.gather(*validation_tasks, return_exceptions=True)
        
        validation_results = {}
        for i, result in enumerate(results):
            url = urls[i]
            if isinstance(result, Exception):
                validation_results[url] = False
            else:
                validation_results[url] = result
                
        return validation_results
        
    async def _validate_single_url(self, url: str) -> bool:
        """Validate a single URL"""
        try:
            response = await self.http_client.get(url)
            
            # Basic validation - check if page contains recipe indicators
            content = response.lower()
            recipe_indicators = [
                'recipe', 'ingredients', 'instructions', 
                'directions', 'cooking', 'preparation'
            ]
            
            return any(indicator in content for indicator in recipe_indicators)
            
        except Exception:
            return False
```

### Step 4: Discovery Engine Core (120 minutes)
Create `recipe_discovery_mcp/discovery_engine.py`:

```python
import asyncio
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .site_manager import SiteManager  
from .url_manager import UrlManager
from .scraper import RecipeScrapingService
from .progress_tracker import ProgressTracker
from .models import RecipeData, DiscoveryJob, DiscoveryResult
from .utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class DiscoveryConfig:
    """Configuration for discovery operations"""
    max_urls_per_site: int = 50
    max_total_concurrent: int = 10
    target_sites: Optional[List[str]] = None
    validate_urls: bool = True
    progress_callback: Optional[Callable] = None

class MultiSiteDiscoveryEngine:
    def __init__(
        self,
        site_manager: SiteManager,
        url_manager: UrlManager, 
        scraping_service: RecipeScrapingService,
        progress_tracker: ProgressTracker
    ):
        self.site_manager = site_manager
        self.url_manager = url_manager  
        self.scraping_service = scraping_service
        self.progress_tracker = progress_tracker
        
    async def discover_recipes(
        self, 
        query: str,
        config: DiscoveryConfig
    ) -> DiscoveryResult:
        """Main entry point for multi-site recipe discovery"""
        
        job = DiscoveryJob(
            query=query,
            config=config,
            started_at=datetime.now()
        )
        
        logger.info(f"Starting recipe discovery for query: {query}")
        
        try:
            # Phase 1: URL Discovery
            await self.progress_tracker.update_phase("url_discovery")
            discovered_urls = await self.url_manager.discover_recipe_urls(
                query=query,
                max_urls_per_site=config.max_urls_per_site,
                sites=config.target_sites
            )
            
            # Phase 2: URL Validation (optional)
            validated_urls = discovered_urls
            if config.validate_urls:
                await self.progress_tracker.update_phase("url_validation")
                validated_urls = await self._validate_discovered_urls(discovered_urls)
                
            # Phase 3: Recipe Scraping
            await self.progress_tracker.update_phase("recipe_scraping")
            scraping_results = await self._scrape_discovered_recipes(
                validated_urls, config
            )
            
            # Phase 4: Result Aggregation
            await self.progress_tracker.update_phase("result_aggregation")
            result = self._aggregate_results(job, scraping_results, validated_urls)
            
            logger.info(f"Discovery completed: {result.summary}")
            return result
            
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            raise
            
    async def _validate_discovered_urls(
        self, 
        discovered_urls: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Validate discovered URLs"""
        
        validated_urls = {}
        
        for site_domain, urls in discovered_urls.items():
            if not urls:
                validated_urls[site_domain] = []
                continue
                
            logger.info(f"Validating {len(urls)} URLs for {site_domain}")
            
            # Update progress
            await self.progress_tracker.update_site_progress(
                site_domain, "validating", 0, len(urls)
            )
            
            validation_results = await self.url_manager.validate_urls(urls)
            valid_urls = [url for url, is_valid in validation_results.items() if is_valid]
            
            validated_urls[site_domain] = valid_urls
            
            await self.progress_tracker.update_site_progress(
                site_domain, "validated", len(valid_urls), len(urls)
            )
            
            logger.info(f"Validated {len(valid_urls)}/{len(urls)} URLs for {site_domain}")
            
        return validated_urls
        
    async def _scrape_discovered_recipes(
        self,
        validated_urls: Dict[str, List[str]],
        config: DiscoveryConfig
    ) -> Dict[str, List[RecipeData]]:
        """Scrape recipes from validated URLs"""
        
        scraping_results = {}
        
        # Create semaphore for global concurrency control
        global_semaphore = asyncio.Semaphore(config.max_total_concurrent)
        
        scraping_tasks = []
        for site_domain, urls in validated_urls.items():
            if not urls:
                scraping_results[site_domain] = []
                continue
                
            task = self._scrape_site_recipes(
                site_domain, urls, global_semaphore
            )
            scraping_tasks.append(task)
            
        results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            site_domain = list(validated_urls.keys())[i]
            if isinstance(result, Exception):
                logger.error(f"Scraping failed for {site_domain}: {result}")
                scraping_results[site_domain] = []
            else:
                scraping_results[site_domain] = result
                
        return scraping_results
        
    async def _scrape_site_recipes(
        self,
        site_domain: str,
        urls: List[str], 
        global_semaphore: asyncio.Semaphore
    ) -> List[RecipeData]:
        """Scrape recipes for a specific site"""
        
        site_config = self.site_manager.sites.get(site_domain)
        if not site_config:
            logger.error(f"No configuration found for {site_domain}")
            return []
            
        logger.info(f"Scraping {len(urls)} recipes from {site_domain}")
        
        # Update progress
        await self.progress_tracker.update_site_progress(
            site_domain, "scraping", 0, len(urls)
        )
        
        # Create site-specific semaphore
        site_semaphore = asyncio.Semaphore(site_config.max_concurrent)
        
        async def scrape_with_limits(url: str) -> RecipeData:
            async with global_semaphore:
                async with site_semaphore:
                    # Respect site rate limiting
                    await asyncio.sleep(1.0 / site_config.rate_limit)
                    return await self.scraping_service.scrape_recipe(url)
        
        # Execute scraping tasks
        scraping_tasks = [scrape_with_limits(url) for url in urls]
        results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        
        # Process results
        recipe_data = []
        successful_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scraping error: {result}")
                # Create failed recipe data
                recipe_data.append(RecipeData(
                    url="unknown",
                    success=False,
                    error_message=str(result)
                ))
            else:
                recipe_data.append(result)
                if result.success:
                    successful_count += 1
                    
        # Update final progress
        await self.progress_tracker.update_site_progress(
            site_domain, "completed", successful_count, len(urls)
        )
        
        logger.info(f"Completed scraping for {site_domain}: {successful_count}/{len(urls)} successful")
        
        return recipe_data
        
    def _aggregate_results(
        self,
        job: DiscoveryJob,
        scraping_results: Dict[str, List[RecipeData]],
        validated_urls: Dict[str, List[str]]
    ) -> DiscoveryResult:
        """Aggregate all results into final result object"""
        
        all_recipes = []
        site_summaries = {}
        
        for site_domain, recipes in scraping_results.items():
            all_recipes.extend(recipes)
            
            successful_recipes = [r for r in recipes if r.success]
            site_summaries[site_domain] = {
                "total_urls": len(validated_urls.get(site_domain, [])),
                "scraped_recipes": len(recipes),
                "successful_recipes": len(successful_recipes),
                "success_rate": len(successful_recipes) / len(recipes) if recipes else 0
            }
            
        return DiscoveryResult(
            job=job,
            recipes=all_recipes,
            site_summaries=site_summaries,
            completed_at=datetime.now()
        )
```

### Step 5: Progress Tracking System (75 minutes)
Create `recipe_discovery_mcp/progress_tracker.py`:

```python
import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class DiscoveryPhase(str, Enum):
    URL_DISCOVERY = "url_discovery"
    URL_VALIDATION = "url_validation" 
    RECIPE_SCRAPING = "recipe_scraping"
    RESULT_AGGREGATION = "result_aggregation"
    COMPLETED = "completed"

@dataclass
class SiteProgress:
    site_domain: str
    status: str = "pending"
    completed: int = 0
    total: int = 0
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def percentage(self) -> float:
        return (self.completed / self.total * 100) if self.total > 0 else 0.0
        
    @property
    def is_complete(self) -> bool:
        return self.completed >= self.total and self.total > 0

@dataclass 
class OverallProgress:
    current_phase: DiscoveryPhase = DiscoveryPhase.URL_DISCOVERY
    site_progress: Dict[str, SiteProgress] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def overall_percentage(self) -> float:
        if not self.site_progress:
            return 0.0
            
        total_percentage = sum(progress.percentage for progress in self.site_progress.values())
        return total_percentage / len(self.site_progress)
        
    @property
    def is_complete(self) -> bool:
        return (self.current_phase == DiscoveryPhase.COMPLETED and 
                all(progress.is_complete for progress in self.site_progress.values()))

class ProgressTracker:
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.progress = OverallProgress()
        self._lock = asyncio.Lock()
        
    async def update_phase(self, phase: DiscoveryPhase):
        """Update the current discovery phase"""
        async with self._lock:
            self.progress.current_phase = phase
            self.progress.last_updated = datetime.now()
            
        await self._notify_progress()
        
    async def update_site_progress(
        self,
        site_domain: str,
        status: str,
        completed: int,
        total: int
    ):
        """Update progress for a specific site"""
        async with self._lock:
            if site_domain not in self.progress.site_progress:
                self.progress.site_progress[site_domain] = SiteProgress(
                    site_domain=site_domain,
                    started_at=datetime.now()
                )
                
            site_progress = self.progress.site_progress[site_domain]
            site_progress.status = status
            site_progress.completed = completed
            site_progress.total = total
            site_progress.updated_at = datetime.now()
            
            self.progress.last_updated = datetime.now()
            
        await self._notify_progress()
        
    async def _notify_progress(self):
        """Notify progress callback if configured"""
        if self.progress_callback:
            try:
                await self.progress_callback(self.get_progress_summary())
            except Exception as e:
                # Don't let progress notification errors break discovery
                print(f"Progress notification error: {e}")
                
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary"""
        return {
            "phase": self.progress.current_phase.value,
            "overall_percentage": round(self.progress.overall_percentage, 1),
            "sites": {
                domain: {
                    "status": progress.status,
                    "completed": progress.completed,
                    "total": progress.total,
                    "percentage": round(progress.percentage, 1)
                }
                for domain, progress in self.progress.site_progress.items()
            },
            "started_at": self.progress.started_at.isoformat(),
            "last_updated": self.progress.last_updated.isoformat(),
            "is_complete": self.progress.is_complete
        }
        
    async def mark_complete(self):
        """Mark discovery as complete"""
        await self.update_phase(DiscoveryPhase.COMPLETED)
```

### Step 6: Enhanced Data Models (45 minutes)
Update `models.py` with discovery-specific models:

```python
# Add to existing models.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class SiteConfig:
    """Configuration for a recipe site"""
    domain: str
    name: str
    base_url: str
    rate_limit: float = 2.0
    timeout: int = 30
    max_concurrent: int = 5
    search_paths: List[str] = None
    recipe_url_patterns: List[str] = None
    priority: str = "medium"  # high, medium, low
    enabled: bool = True
    
    def __post_init__(self):
        if self.search_paths is None:
            self.search_paths = []
        if self.recipe_url_patterns is None:
            self.recipe_url_patterns = []

@dataclass
class DiscoveryJob:
    """Represents a discovery job"""
    query: str
    config: 'DiscoveryConfig'
    started_at: datetime
    job_id: str = None
    
    def __post_init__(self):
        if self.job_id is None:
            import uuid
            self.job_id = str(uuid.uuid4())[:8]

@dataclass
class DiscoveryResult:
    """Results from multi-site discovery operation"""
    job: DiscoveryJob
    recipes: List[RecipeData]
    site_summaries: Dict[str, Dict[str, Any]]
    completed_at: datetime
    
    @property
    def summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        successful_recipes = [r for r in self.recipes if r.success]
        
        return {
            "query": self.job.query,
            "total_recipes": len(self.recipes),
            "successful_recipes": len(successful_recipes),
            "success_rate": len(successful_recipes) / len(self.recipes) if self.recipes else 0,
            "sites_scraped": len(self.site_summaries),
            "duration_seconds": (self.completed_at - self.job.started_at).total_seconds()
        }
```

### Step 7: MCP Tool Integration (90 minutes)
Update `server.py` with discovery engine tools:

```python
# Add to existing server.py

from .discovery_engine import MultiSiteDiscoveryEngine, DiscoveryConfig
from .site_manager import SiteManager
from .url_manager import UrlManager
from .progress_tracker import ProgressTracker

# Initialize discovery components
site_manager = SiteManager()
url_manager = UrlManager(site_manager, http_client)  
progress_tracker = ProgressTracker()
discovery_engine = MultiSiteDiscoveryEngine(
    site_manager, url_manager, scraping_service, progress_tracker
)

@tool("discover_recipes")
async def discover_recipes(
    query: str,
    max_urls_per_site: int = 50,
    sites: Optional[List[str]] = None,
    validate_urls: bool = True
) -> Dict[str, Any]:
    """Discover recipes across multiple sites for a query"""
    
    config = DiscoveryConfig(
        max_urls_per_site=max_urls_per_site,
        target_sites=sites,
        validate_urls=validate_urls
    )
    
    result = await discovery_engine.discover_recipes(query, config)
    
    return {
        "job_id": result.job.job_id,
        "query": query,
        "summary": result.summary,
        "recipes": [recipe.to_json() for recipe in result.recipes],
        "site_summaries": result.site_summaries
    }

@tool("get_available_sites")
async def get_available_sites() -> Dict[str, Any]:
    """Get list of available recipe sites"""
    sites = site_manager.get_enabled_sites()
    
    return {
        "sites": [
            {
                "domain": site.domain,
                "name": site.name,
                "priority": site.priority,
                "rate_limit": site.rate_limit,
                "max_concurrent": site.max_concurrent
            }
            for site in sites
        ],
        "total_sites": len(sites)
    }

@tool("discover_urls_only") 
async def discover_urls_only(
    query: str,
    max_urls_per_site: int = 50,
    sites: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Discover recipe URLs without scraping content"""
    
    discovered_urls = await url_manager.discover_recipe_urls(
        query=query,
        max_urls_per_site=max_urls_per_site,
        sites=sites
    )
    
    total_urls = sum(len(urls) for urls in discovered_urls.values())
    
    return {
        "query": query,
        "discovered_urls": discovered_urls,
        "total_urls": total_urls,
        "sites_searched": len(discovered_urls)
    }

@tool("test_discovery_engine")
async def test_discovery_engine() -> Dict[str, Any]:
    """Test discovery engine with a simple query"""
    
    test_query = "chicken recipe"
    config = DiscoveryConfig(
        max_urls_per_site=5,
        target_sites=["allrecipes.com"],
        validate_urls=False
    )
    
    result = await discovery_engine.discover_recipes(test_query, config)
    
    return {
        "test_query": test_query,
        "test_result": result.summary,
        "engine_status": "operational" if result.recipes else "error"
    }
```

### Step 8: Testing Framework (90 minutes)
Create comprehensive tests for discovery engine:

#### Unit Tests (`tests/unit/test_discovery_engine.py`):
```python
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine, DiscoveryConfig
from recipe_discovery_mcp.models import SiteConfig, RecipeData

class TestDiscoveryEngine:
    @pytest.fixture
    def mock_components(self):
        site_manager = MagicMock()
        url_manager = MagicMock()
        scraping_service = MagicMock()
        progress_tracker = MagicMock()
        
        return site_manager, url_manager, scraping_service, progress_tracker
        
    @pytest.fixture
    def discovery_engine(self, mock_components):
        return MultiSiteDiscoveryEngine(*mock_components)
        
    @pytest.mark.asyncio
    async def test_discover_recipes_success(self, discovery_engine, mock_components):
        """Test successful recipe discovery"""
        site_manager, url_manager, scraping_service, progress_tracker = mock_components
        
        # Mock URL discovery
        url_manager.discover_recipe_urls.return_value = {
            "allrecipes.com": ["https://allrecipes.com/recipe/1", "https://allrecipes.com/recipe/2"]
        }
        
        # Mock scraping
        scraping_service.scrape_recipe.return_value = RecipeData(
            url="https://allrecipes.com/recipe/1",
            title="Test Recipe",
            success=True
        )
        
        config = DiscoveryConfig(max_urls_per_site=5)
        result = await discovery_engine.discover_recipes("test query", config)
        
        assert result.summary["successful_recipes"] > 0
        assert "allrecipes.com" in result.site_summaries
        
    @pytest.mark.asyncio
    async def test_concurrent_site_processing(self, discovery_engine):
        """Test that multiple sites are processed concurrently"""
        # Implementation testing concurrent processing
        pass
```

#### Integration Tests (`tests/integration/test_full_discovery.py`):
```python
import pytest
from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine, DiscoveryConfig

class TestFullDiscovery:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_real_discovery_small_scale(self):
        """Test real discovery with minimal queries"""
        # Test with actual sites but limited scope
        pass
        
    @pytest.mark.asyncio  
    async def test_error_isolation(self):
        """Test that errors in one site don't affect others"""
        # Implementation testing error isolation
        pass
```

### Step 9: Performance Optimization (60 minutes)
Implement performance monitoring and optimization:

#### Memory Management:
- Implement streaming result processing for large batches
- Add memory usage monitoring and warnings
- Optimize data structures for large-scale operations

#### Concurrency Tuning:
- Dynamic concurrency adjustment based on site response times
- Adaptive rate limiting based on site responses
- Resource pooling for HTTP connections

### Step 10: Documentation and Integration Testing (45 minutes)
- Update README with multi-site discovery examples
- Create user guide for site configuration
- Validate end-to-end workflow with Claude Desktop
- Performance testing with realistic workloads

## Acceptance Criteria

### Functional Requirements ✅
- [ ] Discover recipe URLs across 3+ configured sites simultaneously
- [ ] Handle 100+ recipes across 10+ sites with proper resource management
- [ ] Support configurable site lists and URL limits
- [ ] Provide real-time progress reporting during discovery
- [ ] Handle site-specific rate limiting and error isolation
- [ ] Successfully scrape discovered recipes with 90%+ success rate

### Technical Requirements ✅
- [ ] Proper concurrent processing with configurable limits
- [ ] Site-specific configuration system with JSON config files
- [ ] URL validation and filtering based on site patterns
- [ ] Comprehensive error handling with per-site isolation
- [ ] Resource cleanup and memory management for large operations
- [ ] Integration with existing scraping service from Issue #6

### Integration Requirements ✅
- [ ] Builds on Issue #6 scraping functionality
- [ ] Uses Issue #5 server foundation and error handling
- [ ] Integrates with Claude Desktop through MCP tools
- [ ] Supports downstream eKitchen Database MCP integration
- [ ] Compatible with conversational workflow patterns
- [ ] Provides structured JSON output for further processing

### Quality Requirements ✅
- [ ] Code coverage >85% for core discovery functionality
- [ ] Performance supports 100+ recipes in <10 minutes across multiple sites
- [ ] Memory usage remains stable during large batch operations
- [ ] Error isolation prevents cascading failures
- [ ] Comprehensive logging and monitoring of discovery operations

## Performance Expectations

### Throughput Targets
- **Multi-site Discovery**: 100+ recipes across 5+ sites in <10 minutes
- **URL Discovery**: 50+ URLs per site in <2 minutes
- **Concurrent Sites**: 5+ sites processed simultaneously
- **Error Recovery**: Individual site failures don't impact overall operation

### Resource Usage
- **Memory**: <200MB for large discovery operations (100+ recipes)
- **CPU**: Efficient use of async/await and threading
- **Network**: Respectful rate limiting per site configuration
- **Storage**: Minimal temporary data with streaming processing

## Integration Notes

### Completes Recipe Discovery MVP ✅
- Provides full multi-site recipe discovery capability
- Enables conversational recipe discovery through Claude Desktop
- Supports production-scale recipe data collection
- Ready for downstream processing by eKitchen Database MCP

### Establishes Scalable Architecture ✅
- Site configuration system supports easy addition of new sites
- Concurrent processing architecture scales with available resources
- Progress tracking enables monitoring and optimization
- Error isolation ensures robust operation

---

**Blocked until Issues #5 and #6 completion**  
**Final core component for Recipe Discovery MCP MVP**  
**Expected completion: 8-10 hours after dependencies met**  