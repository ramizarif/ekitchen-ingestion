"""
Analytics endpoints for cost tracking and monitoring.

Provides endpoints to query cost metrics, usage statistics, and trends
for video recipe ingestion.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for demo (replace with database in production)
_cost_records = []


def record_extraction_cost(extraction_result: dict):
    """
    Record cost data for an extraction.

    This should be called after each video extraction to track costs.

    Args:
        extraction_result: Dict with extraction metadata including cost_breakdown
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "url": extraction_result.get("url", "unknown"),
        "platform": extraction_result.get("platform", "unknown"),
        "extraction_method": extraction_result.get("extraction_method"),
        "cost_breakdown": extraction_result.get("cost_breakdown", {}),
        "frames_used": extraction_result.get("frames_used", 0),
        "audio_duration_seconds": extraction_result.get("audio_duration_seconds", 0),
        "processing_time_ms": extraction_result.get("processing_time_ms", 0),
        "success": extraction_result.get("success", False)
    }
    _cost_records.append(record)
    logger.info("video_ingestion_cost", extra=record)


@router.get("/analytics/costs")
async def get_cost_analytics(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    platform: Optional[str] = Query(None, description="Filter by platform (tiktok, instagram, youtube)")
):
    """
    Get cost analytics for video ingestion.

    Returns:
    - Total costs by time period
    - Breakdown by extraction method
    - Platform-specific costs
    - Average cost per video
    - Cost trends

    Example:
        GET /api/v1/analytics/costs?start_date=2025-01-01&platform=tiktok
    """
    try:
        # Filter records by date range
        filtered_records = _cost_records

        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            filtered_records = [
                r for r in filtered_records
                if datetime.fromisoformat(r["timestamp"]) >= start_dt
            ]

        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            filtered_records = [
                r for r in filtered_records
                if datetime.fromisoformat(r["timestamp"]) <= end_dt
            ]

        if platform:
            filtered_records = [
                r for r in filtered_records
                if r.get("platform") == platform
            ]

        # Calculate totals
        total_whisper = sum(r["cost_breakdown"].get("whisper_transcription", 0) for r in filtered_records)
        total_gpt4_text = sum(r["cost_breakdown"].get("gpt4_text", 0) for r in filtered_records)
        total_gpt4_vision = sum(r["cost_breakdown"].get("gpt4_vision", 0) for r in filtered_records)
        total_cost = sum(r["cost_breakdown"].get("total", 0) for r in filtered_records)

        # Breakdown by method
        by_method = {}
        for method in ["audio_only", "hybrid", "vision_only"]:
            method_records = [r for r in filtered_records if r.get("extraction_method") == method]
            if method_records:
                by_method[method] = {
                    "count": len(method_records),
                    "total_cost": sum(r["cost_breakdown"].get("total", 0) for r in method_records),
                    "avg_cost": sum(r["cost_breakdown"].get("total", 0) for r in method_records) / len(method_records)
                }

        # Breakdown by platform
        by_platform = {}
        for plat in ["tiktok", "instagram", "youtube"]:
            plat_records = [r for r in filtered_records if r.get("platform") == plat]
            if plat_records:
                by_platform[plat] = {
                    "count": len(plat_records),
                    "total_cost": sum(r["cost_breakdown"].get("total", 0) for r in plat_records),
                    "avg_cost": sum(r["cost_breakdown"].get("total", 0) for r in plat_records) / len(plat_records)
                }

        # Daily costs (last 7 days)
        daily_costs = {}
        for i in range(7):
            day = (datetime.now() - timedelta(days=i)).date().isoformat()
            day_records = [
                r for r in filtered_records
                if datetime.fromisoformat(r["timestamp"]).date().isoformat() == day
            ]
            daily_costs[day] = sum(r["cost_breakdown"].get("total", 0) for r in day_records)

        return {
            "period": {
                "start": start_date or "all_time",
                "end": end_date or "now"
            },
            "totals": {
                "whisper": round(total_whisper, 4),
                "gpt4_text": round(total_gpt4_text, 4),
                "gpt4_vision": round(total_gpt4_vision, 4),
                "total": round(total_cost, 4),
                "count": len(filtered_records)
            },
            "by_method": by_method,
            "by_platform": by_platform,
            "trends": {
                "daily_costs": daily_costs
            },
            "avg_cost_per_video": round(total_cost / len(filtered_records), 4) if filtered_records else 0.0
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        logger.error(f"Error calculating cost analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics/costs/summary")
async def get_cost_summary():
    """
    Get a quick cost summary for the current day, week, and month.

    Returns:
    - Today's total cost
    - This week's total cost
    - This month's total cost
    - Average cost per video
    """
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Filter records
        today_records = [
            r for r in _cost_records
            if datetime.fromisoformat(r["timestamp"]) >= today_start
        ]
        week_records = [
            r for r in _cost_records
            if datetime.fromisoformat(r["timestamp"]) >= week_start
        ]
        month_records = [
            r for r in _cost_records
            if datetime.fromisoformat(r["timestamp"]) >= month_start
        ]

        # Calculate costs
        today_cost = sum(r["cost_breakdown"].get("total", 0) for r in today_records)
        week_cost = sum(r["cost_breakdown"].get("total", 0) for r in week_records)
        month_cost = sum(r["cost_breakdown"].get("total", 0) for r in month_records)

        # Method distribution (today)
        method_dist = {}
        for method in ["audio_only", "hybrid", "vision_only"]:
            count = len([r for r in today_records if r.get("extraction_method") == method])
            method_dist[method] = {
                "count": count,
                "percentage": round(count / len(today_records) * 100, 1) if today_records else 0
            }

        return {
            "today": {
                "cost": round(today_cost, 2),
                "count": len(today_records)
            },
            "this_week": {
                "cost": round(week_cost, 2),
                "count": len(week_records)
            },
            "this_month": {
                "cost": round(month_cost, 2),
                "count": len(month_records)
            },
            "avg_per_video": round(month_cost / len(month_records), 4) if month_records else 0.0,
            "method_distribution": method_dist
        }

    except Exception as e:
        logger.error(f"Error calculating cost summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/analytics/health")
async def get_analytics_health():
    """
    Check analytics system health.

    Returns:
    - Number of records stored
    - Oldest and newest record timestamps
    - Storage status
    """
    if not _cost_records:
        return {
            "status": "healthy",
            "records_count": 0,
            "message": "No cost records yet"
        }

    timestamps = [datetime.fromisoformat(r["timestamp"]) for r in _cost_records]
    oldest = min(timestamps)
    newest = max(timestamps)

    return {
        "status": "healthy",
        "records_count": len(_cost_records),
        "oldest_record": oldest.isoformat(),
        "newest_record": newest.isoformat(),
        "retention_days": (newest - oldest).days
    }
