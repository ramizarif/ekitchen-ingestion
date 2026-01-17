"""
Search URL Discovery Engine for Recipe Discovery MCP

Intelligently discovers search endpoints for recipe sites using multiple strategies
when hardcoded search paths fail or are unavailable.
"""

import logging
from typing import List, Optional
from urllib.parse import urljoin, urlparse
import asyncio

from bs4 import BeautifulSoup

from .models import SiteConfig
from .http_client import AsyncHttpClient


class SearchUrlDiscoverer:
    """Intelligently discover search endpoints for recipe sites"""
    
    def __init__(self, http_client: AsyncHttpClient):
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
        
    async def discover_search_endpoint(self, site: SiteConfig) -> List[str]:
        """Discover valid search endpoints using multiple strategies"""
        discovered_urls = []
        
        try:
            # Strategy 1: Common pattern testing
            self.logger.debug(f"Testing common patterns for {site.domain}")
            common_patterns = await self._try_common_patterns(site)
            discovered_urls.extend(common_patterns)
            
            # Strategy 2: Homepage form analysis  
            self.logger.debug(f"Analyzing search forms for {site.domain}")
            form_urls = await self._analyze_search_forms(site)
            discovered_urls.extend(form_urls)
            
            # Strategy 3: Navigation parsing
            self.logger.debug(f"Parsing navigation links for {site.domain}")
            nav_urls = await self._parse_navigation_links(site)
            discovered_urls.extend(nav_urls)
            
            # Strategy 4: robots.txt/sitemap analysis
            self.logger.debug(f"Analyzing sitemaps for {site.domain}")
            sitemap_urls = await self._analyze_sitemaps(site)
            discovered_urls.extend(sitemap_urls)
            
            # Validate and rank discovered URLs
            validated_urls = await self._validate_and_rank_urls(discovered_urls, site)
            
            self.logger.info(f"Discovered {len(validated_urls)} search endpoints for {site.domain}")
            return validated_urls
            
        except Exception as e:
            self.logger.error(f"Search endpoint discovery failed for {site.domain}: {e}")
            return []
        
    async def _try_common_patterns(self, site: SiteConfig) -> List[str]:
        """Test common search URL patterns"""
        patterns = [
            "/search", "/search/", "/search/recipes", "/recipes/search",
            "/find", "/find/", "/lookup", "/query", "/s", "/recipe-search"
        ]
        
        valid_patterns = []
        
        for pattern in patterns:
            try:
                test_url = urljoin(site.base_url, pattern)
                if await self._test_search_url(test_url, site):
                    valid_patterns.append(pattern + "?q={query}")
                    
            except Exception as e:
                self.logger.debug(f"Pattern test failed for {pattern} on {site.domain}: {e}")
                continue
                
        return valid_patterns
        
    async def _test_search_url(self, test_url: str, site: SiteConfig) -> bool:
        """Test if a search URL is valid and responsive"""
        try:
            # Test with a simple query
            test_query_url = test_url + "?q=test"
            response = await self.http_client.get(test_query_url)
            
            # Consider 200 or 302 as valid (redirects are common for search)
            if response.status_code in [200, 302]:
                return True
                
        except Exception:
            pass
            
        return False
        
    async def _analyze_search_forms(self, site: SiteConfig) -> List[str]:
        """Parse homepage for search forms and extract action URLs"""
        try:
            response = await self.http_client.get(site.base_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
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
                        elif not action.startswith('http'):
                            action = urljoin(site.base_url, action)
                        
                        # Build search URL template
                        input_name = self._get_search_input_name(form)
                        if input_name:
                            if method == 'GET':
                                search_urls.append(f"{action}?{input_name}={{query}}")
                            # Note: POST forms could be handled in future enhancement
                                
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
        
    async def _parse_navigation_links(self, site: SiteConfig) -> List[str]:
        """Parse navigation for search-related links"""
        try:
            response = await self.http_client.get(site.base_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            search_urls = []
            
            # Look for navigation elements
            nav_elements = soup.find_all(['nav', 'header', 'menu'])
            nav_elements.extend(soup.find_all('div', class_=['nav', 'navigation', 'menu', 'header']))
            
            for nav in nav_elements:
                links = nav.find_all('a', href=True)
                for link in links:
                    href = link['href']
                    link_text = link.get_text().lower().strip()
                    
                    # Look for search-related link text
                    if any(term in link_text for term in ['search', 'find', 'lookup']):
                        if href.startswith('/'):
                            href = urljoin(site.base_url, href)
                        elif not href.startswith('http'):
                            href = urljoin(site.base_url, href)
                            
                        # Convert to search URL template
                        if '?' in href:
                            search_urls.append(href + "&q={query}")
                        else:
                            search_urls.append(href + "?q={query}")
                            
            return search_urls
            
        except Exception as e:
            self.logger.error(f"Failed to parse navigation for {site.domain}: {e}")
            return []
            
    async def _analyze_sitemaps(self, site: SiteConfig) -> List[str]:
        """Analyze robots.txt and sitemap for search endpoints"""
        try:
            search_urls = []
            
            # Check robots.txt for sitemap references
            robots_url = urljoin(site.base_url, '/robots.txt')
            try:
                response = await self.http_client.get(robots_url)
                if response.status_code == 200:
                    # Look for search-related paths in robots.txt
                    for line in response.text.split('\n'):
                        line = line.strip().lower()
                        if ('disallow:' in line or 'allow:' in line) and 'search' in line:
                            # Extract path from robots.txt entry
                            path = line.split(':', 1)[1].strip()
                            if path.startswith('/'):
                                search_urls.append(path + "?q={query}")
                                
            except Exception:
                pass
                
            # Check common sitemap locations
            sitemap_urls = ['/sitemap.xml', '/sitemap_index.xml', '/sitemap.txt']
            for sitemap_path in sitemap_urls:
                try:
                    sitemap_url = urljoin(site.base_url, sitemap_path)
                    response = await self.http_client.get(sitemap_url)
                    if response.status_code == 200:
                        # Parse XML sitemap for search URLs
                        soup = BeautifulSoup(response.text, 'xml')
                        for loc in soup.find_all('loc'):
                            if loc.text and 'search' in loc.text.lower():
                                parsed_url = urlparse(loc.text)
                                if parsed_url.path:
                                    search_urls.append(parsed_url.path + "?q={query}")
                                    
                except Exception:
                    continue
                    
            return search_urls
            
        except Exception as e:
            self.logger.error(f"Failed to analyze sitemaps for {site.domain}: {e}")
            return []
            
    async def _validate_and_rank_urls(self, discovered_urls: List[str], site: SiteConfig) -> List[str]:
        """Validate discovered URLs and rank by effectiveness"""
        if not discovered_urls:
            return []
            
        # Remove duplicates while preserving order
        unique_urls = []
        seen = set()
        for url in discovered_urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
                
        # Test each URL and rank by response quality
        validated_urls = []
        
        for url_template in unique_urls:
            try:
                # Test with a sample query
                test_url = url_template.format(query="test")
                full_url = urljoin(site.base_url, test_url) if not test_url.startswith('http') else test_url
                
                response = await self.http_client.get(full_url)
                
                # Rank by status code quality
                if response.status_code == 200:
                    validated_urls.insert(0, url_template)  # Best responses first
                elif response.status_code in [302, 301]:
                    validated_urls.append(url_template)     # Redirects second
                    
            except Exception:
                # Don't include URLs that completely fail
                continue
                
        return validated_urls