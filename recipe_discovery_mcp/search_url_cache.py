"""
Persistent Caching System for Search URL Discovery

Provides thread-safe caching of discovered search URLs with success tracking,
TTL management, and persistent storage across application restarts.
"""

import json
import asyncio
import logging
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
        self.logger = logging.getLogger(__name__)
        
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
                    
                    self.logger.info(f"Loaded search URL cache with {len(self.cache_data)} entries")
                else:
                    self.logger.info("No existing cache file found, starting with empty cache")
                    
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
                    
                self.logger.debug(f"Saved search URL cache to {self.cache_file}")
                    
            except Exception as e:
                self.logger.error(f"Failed to save search URL cache: {e}")
                
    async def get_cached_search_urls(self, domain: str) -> Optional[List[str]]:
        """Get cached search URLs for a domain"""
        async with self._lock:
            if domain not in self.cache_data:
                return None
                
            entry = self.cache_data[domain]
            
            # Check if cache is still valid
            try:
                discovered_at = datetime.fromisoformat(entry['discovered_at'])
                if datetime.now() - discovered_at > self.cache_ttl:
                    self.logger.debug(f"Cache expired for {domain}")
                    return None
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Invalid cache entry for {domain}: {e}")
                return None
                
            search_urls = entry.get('search_urls', [])
            if search_urls:
                self.logger.debug(f"Cache hit for {domain}: {len(search_urls)} URLs")
            
            return search_urls
            
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
        self.logger.info(f"Cached {len(search_urls)} search URLs for {domain}")
        
    async def update_success_rate(self, domain: str, search_url: str, success: bool):
        """Update success rate for a specific search URL"""
        async with self._lock:
            if domain in self.cache_data:
                entry = self.cache_data[domain]
                
                # Update verification count and success rate
                count = entry.get('verification_count', 1)
                current_rate = entry.get('success_rate', 1.0)
                
                # Calculate new success rate using moving average
                total_successes = current_rate * count
                if success:
                    total_successes += 1
                count += 1
                
                entry['success_rate'] = total_successes / count
                entry['verification_count'] = count
                entry['last_verified'] = datetime.now().isoformat()
                
                self.logger.debug(
                    f"Updated success rate for {domain}: {entry['success_rate']:.2f} "
                    f"({count} verifications)"
                )
                
        await self.save_cache()
        
    async def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics"""
        async with self._lock:
            total_entries = len(self.cache_data)
            valid_entries = 0
            expired_entries = 0
            
            current_time = datetime.now()
            success_rates = []
            
            for domain, entry in self.cache_data.items():
                try:
                    discovered_at = datetime.fromisoformat(entry['discovered_at'])
                    if current_time - discovered_at <= self.cache_ttl:
                        valid_entries += 1
                        success_rates.append(entry.get('success_rate', 1.0))
                    else:
                        expired_entries += 1
                except (KeyError, ValueError):
                    expired_entries += 1
                    
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
            
            return {
                'total_entries': total_entries,
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'average_success_rate': avg_success_rate,
                'cache_file_size': self.cache_file.stat().st_size if self.cache_file.exists() else 0
            }
            
    async def clear_expired_entries(self) -> int:
        """Manually clear expired entries and return count cleared"""
        async with self._lock:
            cleared_count = await self._clean_expired_entries()
            
        if cleared_count > 0:
            await self.save_cache()
            
        return cleared_count
        
    async def _clean_expired_entries(self):
        """Remove expired cache entries"""
        current_time = datetime.now()
        expired_domains = []
        
        for domain, entry in self.cache_data.items():
            try:
                discovered_at = datetime.fromisoformat(entry['discovered_at'])
                if current_time - discovered_at > self.cache_ttl:
                    expired_domains.append(domain)
            except (KeyError, ValueError):
                # Invalid entry format, mark for removal
                expired_domains.append(domain)
                
        for domain in expired_domains:
            del self.cache_data[domain]
            
        if expired_domains:
            self.logger.info(f"Cleaned {len(expired_domains)} expired cache entries")
            
        return len(expired_domains)
        
    async def invalidate_domain(self, domain: str) -> bool:
        """Invalidate cache for a specific domain"""
        async with self._lock:
            if domain in self.cache_data:
                del self.cache_data[domain]
                await self.save_cache()
                self.logger.info(f"Invalidated cache for {domain}")
                return True
            return False
            
    async def get_domain_cache_info(self, domain: str) -> Optional[Dict]:
        """Get detailed cache information for a specific domain"""
        async with self._lock:
            if domain not in self.cache_data:
                return None
                
            entry = self.cache_data[domain].copy()
            
            # Add computed fields
            try:
                discovered_at = datetime.fromisoformat(entry['discovered_at'])
                entry['age_days'] = (datetime.now() - discovered_at).days
                entry['expires_in_days'] = (self.cache_ttl - (datetime.now() - discovered_at)).days
                entry['is_expired'] = datetime.now() - discovered_at > self.cache_ttl
            except (KeyError, ValueError):
                entry['age_days'] = None
                entry['expires_in_days'] = None
                entry['is_expired'] = True
                
            return entry
            
    async def bulk_update_success_rates(self, updates: List[Dict[str, any]]):
        """Bulk update success rates for multiple domains/URLs"""
        async with self._lock:
            for update in updates:
                domain = update.get('domain')
                success = update.get('success', True)
                
                if domain and domain in self.cache_data:
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
        self.logger.info(f"Bulk updated success rates for {len(updates)} entries")