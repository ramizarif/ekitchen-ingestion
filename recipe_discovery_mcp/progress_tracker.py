"""Progress Tracking System for Recipe Discovery MCP

Provides real-time progress tracking and reporting for multi-site
recipe discovery operations with phase management and statistics.
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog

from .utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryPhase(str, Enum):
    """Enumeration of discovery operation phases"""
    INITIALIZING = "initializing"
    URL_DISCOVERY = "url_discovery"
    URL_VALIDATION = "url_validation" 
    RECIPE_SCRAPING = "recipe_scraping"
    RESULT_AGGREGATION = "result_aggregation"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class SiteProgress:
    """Progress tracking for individual sites"""
    site_domain: str
    status: str = "pending"
    completed: int = 0
    total: int = 0
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    current_phase: str = "pending"
    error_count: int = 0
    last_error: Optional[str] = None
    
    @property
    def percentage(self) -> float:
        """Calculate completion percentage"""
        return (self.completed / self.total * 100) if self.total > 0 else 0.0
        
    @property
    def is_complete(self) -> bool:
        """Check if site processing is complete"""
        return self.completed >= self.total and self.total > 0
        
    @property
    def is_active(self) -> bool:
        """Check if site is currently being processed"""
        return self.status in ["discovering", "validating", "scraping"]
        
    @property
    def success_rate(self) -> float:
        """Calculate success rate (completed vs errors)"""
        if self.completed + self.error_count == 0:
            return 100.0
        return (self.completed / (self.completed + self.error_count)) * 100
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "site_domain": self.site_domain,
            "status": self.status,
            "completed": self.completed,
            "total": self.total,
            "percentage": round(self.percentage, 1),
            "current_phase": self.current_phase,
            "error_count": self.error_count,
            "success_rate": round(self.success_rate, 1),
            "is_complete": self.is_complete,
            "is_active": self.is_active,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_error": self.last_error
        }


@dataclass 
class OverallProgress:
    """Overall progress tracking for discovery operations"""
    job_id: str
    query: str
    current_phase: DiscoveryPhase = DiscoveryPhase.INITIALIZING
    site_progress: Dict[str, SiteProgress] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    total_sites: int = 0
    completed_sites: int = 0
    failed_sites: int = 0
    total_urls: int = 0
    completed_urls: int = 0
    successful_recipes: int = 0
    
    @property
    def overall_percentage(self) -> float:
        """Calculate overall completion percentage"""
        if not self.site_progress:
            return 0.0
            
        total_percentage = sum(progress.percentage for progress in self.site_progress.values())
        return total_percentage / len(self.site_progress) if self.site_progress else 0.0
        
    @property
    def is_complete(self) -> bool:
        """Check if overall discovery is complete"""
        return (self.current_phase == DiscoveryPhase.COMPLETED and 
                all(progress.is_complete for progress in self.site_progress.values()))
                
    @property
    def active_sites_count(self) -> int:
        """Count of sites currently being processed"""
        return sum(1 for progress in self.site_progress.values() if progress.is_active)
        
    @property
    def overall_success_rate(self) -> float:
        """Calculate overall success rate across all sites"""
        if self.completed_urls + self._total_errors() == 0:
            return 100.0
        return (self.successful_recipes / (self.completed_urls + self._total_errors())) * 100
        
    def _total_errors(self) -> int:
        """Calculate total errors across all sites"""
        return sum(progress.error_count for progress in self.site_progress.values())
        
    @property
    def duration_seconds(self) -> float:
        """Calculate operation duration in seconds"""
        return (self.last_updated - self.started_at).total_seconds()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "job_id": self.job_id,
            "query": self.query,
            "current_phase": self.current_phase.value,
            "overall_percentage": round(self.overall_percentage, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "total_sites": self.total_sites,
            "completed_sites": self.completed_sites,
            "failed_sites": self.failed_sites,
            "active_sites": self.active_sites_count,
            "total_urls": self.total_urls,
            "completed_urls": self.completed_urls,
            "successful_recipes": self.successful_recipes,
            "overall_success_rate": round(self.overall_success_rate, 1),
            "is_complete": self.is_complete,
            "started_at": self.started_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "sites": {
                domain: progress.to_dict() 
                for domain, progress in self.site_progress.items()
            }
        }


class ProgressTracker:
    """Real-time progress tracker for multi-site discovery operations
    
    Tracks progress across multiple phases and sites with optional
    callback notifications for real-time updates.
    """
    
    def __init__(self, 
                 job_id: str,
                 query: str,
                 progress_callback: Optional[Callable] = None):
        """Initialize progress tracker
        
        Args:
            job_id: Unique identifier for this discovery job
            query: Search query being processed
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback
        self.progress = OverallProgress(job_id=job_id, query=query)
        self._lock = asyncio.Lock()
        self.logger = structlog.get_logger().bind(
            component="progress_tracker",
            job_id=job_id
        )
        
        self.logger.info(
            "Progress tracker initialized",
            job_id=job_id,
            query=query
        )
        
    async def update_phase(self, phase: DiscoveryPhase):
        """Update the current discovery phase
        
        Args:
            phase: New discovery phase
        """
        async with self._lock:
            old_phase = self.progress.current_phase
            self.progress.current_phase = phase
            self.progress.last_updated = datetime.now()
            
        self.logger.info(
            "Discovery phase updated",
            old_phase=old_phase.value,
            new_phase=phase.value
        )
        
        await self._notify_progress()
        
    async def initialize_sites(self, site_domains: List[str]):
        """Initialize site progress tracking
        
        Args:
            site_domains: List of site domains to track
        """
        async with self._lock:
            self.progress.total_sites = len(site_domains)
            
            for domain in site_domains:
                if domain not in self.progress.site_progress:
                    self.progress.site_progress[domain] = SiteProgress(
                        site_domain=domain,
                        started_at=datetime.now()
                    )
                    
            self.progress.last_updated = datetime.now()
            
        self.logger.info(
            "Site progress tracking initialized",
            total_sites=len(site_domains),
            sites=site_domains
        )
        
        await self._notify_progress()
        
    async def update_site_progress(
        self,
        site_domain: str,
        status: str,
        completed: int,
        total: int,
        phase: str = None,
        error: str = None
    ):
        """Update progress for a specific site
        
        Args:
            site_domain: Domain of the site being updated
            status: Current status (discovering, validating, scraping, etc.)
            completed: Number of completed items
            total: Total number of items
            phase: Current processing phase for this site
            error: Error message if applicable
        """
        async with self._lock:
            if site_domain not in self.progress.site_progress:
                self.progress.site_progress[site_domain] = SiteProgress(
                    site_domain=site_domain,
                    started_at=datetime.now()
                )
                
            site_progress = self.progress.site_progress[site_domain]
            
            # Update site progress
            old_completed = site_progress.completed
            site_progress.status = status
            site_progress.completed = completed
            site_progress.total = total
            site_progress.updated_at = datetime.now()
            
            if phase:
                site_progress.current_phase = phase
                
            if error:
                site_progress.error_count += 1
                site_progress.last_error = error
                
            # Update overall progress counters
            self.progress.completed_urls += (completed - old_completed)
            
            # Update site completion status
            self._update_site_completion_counts()
            
            self.progress.last_updated = datetime.now()
            
        self.logger.debug(
            "Site progress updated",
            site_domain=site_domain,
            status=status,
            completed=completed,
            total=total,
            percentage=f"{site_progress.percentage:.1f}%"
        )
        
        await self._notify_progress()
        
    async def update_recipe_success(self, site_domain: str, count: int = 1):
        """Update successful recipe count for a site
        
        Args:
            site_domain: Domain of the site
            count: Number of successful recipes to add
        """
        async with self._lock:
            self.progress.successful_recipes += count
            self.progress.last_updated = datetime.now()
            
        await self._notify_progress()
        
    async def update_total_urls(self, site_domain: str, url_count: int):
        """Update total URL count discovered for a site
        
        Args:
            site_domain: Domain of the site
            url_count: Number of URLs discovered
        """
        async with self._lock:
            self.progress.total_urls += url_count
            
            if site_domain in self.progress.site_progress:
                site_progress = self.progress.site_progress[site_domain]
                site_progress.total = max(site_progress.total, url_count)
                
            self.progress.last_updated = datetime.now()
            
        await self._notify_progress()
        
    def _update_site_completion_counts(self):
        """Update overall site completion counters"""
        completed = 0
        failed = 0
        
        for progress in self.progress.site_progress.values():
            if progress.is_complete:
                if progress.error_count > progress.completed / 2:  # More than 50% errors
                    failed += 1
                else:
                    completed += 1
                    
        self.progress.completed_sites = completed
        self.progress.failed_sites = failed
        
    async def mark_site_failed(self, site_domain: str, error: str):
        """Mark a site as failed
        
        Args:
            site_domain: Domain of the failed site
            error: Error description
        """
        await self.update_site_progress(
            site_domain=site_domain,
            status="failed",
            completed=0,
            total=0,
            error=error
        )
        
        self.logger.warning(
            "Site marked as failed",
            site_domain=site_domain,
            error=error
        )
        
    async def mark_complete(self):
        """Mark discovery as complete"""
        await self.update_phase(DiscoveryPhase.COMPLETED)
        
        self.logger.info(
            "Discovery operation completed",
            job_id=self.progress.job_id,
            duration_seconds=self.progress.duration_seconds,
            successful_recipes=self.progress.successful_recipes,
            overall_success_rate=f"{self.progress.overall_success_rate:.1f}%"
        )
        
    async def mark_error(self, error: str):
        """Mark discovery as failed with error
        
        Args:
            error: Error description
        """
        async with self._lock:
            self.progress.current_phase = DiscoveryPhase.ERROR
            self.progress.last_updated = datetime.now()
            
        self.logger.error(
            "Discovery operation failed",
            job_id=self.progress.job_id,
            error=error
        )
        
        await self._notify_progress()
        
    async def _notify_progress(self):
        """Notify progress callback if configured"""
        if self.progress_callback:
            try:
                progress_data = self.get_progress_summary()
                
                # Handle both sync and async callbacks
                if asyncio.iscoroutinefunction(self.progress_callback):
                    await self.progress_callback(progress_data)
                else:
                    self.progress_callback(progress_data)
                    
            except Exception as e:
                # Don't let progress notification errors break discovery
                self.logger.error(
                    "Progress notification error",
                    error_type=type(e).__name__,
                    error_message=str(e)
                )
                
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get current progress summary
        
        Returns:
            Dictionary with complete progress information
        """
        return self.progress.to_dict()
        
    def get_site_progress(self, site_domain: str) -> Optional[Dict[str, Any]]:
        """Get progress for a specific site
        
        Args:
            site_domain: Domain to get progress for
            
        Returns:
            Site progress dictionary or None if not found
        """
        if site_domain in self.progress.site_progress:
            return self.progress.site_progress[site_domain].to_dict()
        return None
        
    def get_active_sites(self) -> List[str]:
        """Get list of sites currently being processed
        
        Returns:
            List of site domains that are currently active
        """
        return [
            domain for domain, progress in self.progress.site_progress.items()
            if progress.is_active
        ]
        
    def get_stats(self) -> Dict[str, Any]:
        """Get progress tracker statistics
        
        Returns:
            Dictionary with tracker statistics
        """
        return {
            "job_id": self.progress.job_id,
            "query": self.progress.query,
            "duration_seconds": self.progress.duration_seconds,
            "current_phase": self.progress.current_phase.value,
            "total_sites": self.progress.total_sites,
            "completed_sites": self.progress.completed_sites,
            "failed_sites": self.progress.failed_sites,
            "active_sites": self.progress.active_sites_count,
            "total_urls": self.progress.total_urls,
            "completed_urls": self.progress.completed_urls,
            "successful_recipes": self.progress.successful_recipes,
            "overall_percentage": self.progress.overall_percentage,
            "overall_success_rate": self.progress.overall_success_rate,
            "is_complete": self.progress.is_complete
        }
        
    def reset(self):
        """Reset progress tracker for reuse"""
        self.progress.site_progress.clear()
        self.progress.current_phase = DiscoveryPhase.INITIALIZING
        self.progress.started_at = datetime.now()
        self.progress.last_updated = datetime.now()
        self.progress.completed_sites = 0
        self.progress.failed_sites = 0
        self.progress.total_urls = 0
        self.progress.completed_urls = 0
        self.progress.successful_recipes = 0
        
        self.logger.info(
            "Progress tracker reset",
            job_id=self.progress.job_id
        )