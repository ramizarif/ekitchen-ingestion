"""
Smoke tests for video ingestion end-to-end flow.

Run with:
    pytest tests/test_smoke_video_ingestion.py -v -s

Provide a TikTok URL:
    pytest tests/test_smoke_video_ingestion.py -v -s --tiktok-url="https://www.tiktok.com/@user/video/123"

Or use interactive mode (will prompt for URL):
    pytest tests/test_smoke_video_ingestion.py -v -s --interactive
"""
import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
class TestVideoIngestionSmoke:
    """End-to-end smoke tests for video ingestion."""

    async def test_full_video_ingestion_with_cost_tracking(self, tiktok_url):
        """
        Smoke test: Full video ingestion flow with cost tracking.

        Tests:
        1. Video ingestion endpoint accepts TikTok URL
        2. Successfully extracts recipe
        3. Cost tracking fields are populated
        4. Cost breakdown is calculated
        5. Analytics endpoint records the cost
        """
        print(f"\n🎬 Testing with URL: {tiktok_url}")

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: Ingest the video
            print("📥 Step 1: Ingesting video...")
            response = await client.post(
                "/api/v1/ingest",
                json={
                    "url": tiktok_url,
                    "generate_image": False  # Skip image generation for faster test
                }
            )

            # Verify successful ingestion
            if response.status_code != 200:
                error_detail = response.json().get('detail', {})
                error_code = error_detail.get('error_code', 'UNKNOWN')
                error_msg = error_detail.get('error_message', response.text)

                # If it's a download failure, skip test with helpful message
                if error_code == 'DOWNLOAD_FAILED' and 'yt-dlp' in error_msg:
                    pytest.skip(
                        f"TikTok video download failed - video may be deleted/private or yt-dlp needs update.\n"
                        f"Try: pip install -U yt-dlp\n"
                        f"Or use a different TikTok URL.\n"
                        f"Error: {error_msg[:200]}"
                    )

                # Otherwise, fail the test
                assert False, f"Ingestion failed: {response.text}"

            result = response.json()

            print(f"✅ Successfully ingested: {result['recipe_name']}")
            print(f"   - Recipe ID: {result['recipe_id']}")
            print(f"   - Ingredients: {result['ingredients_processed']}")
            print(f"   - Processing time: {result['processing_time_seconds']:.2f}s")

            assert result['success'] is True
            assert result['source_type'] == 'video'
            assert result['recipe_id']
            assert result['recipe_name']

            # NEW: Verify analytics metadata is included in response
            assert 'analytics' in result, "Analytics field missing from response"
            assert result['analytics'] is not None, "Analytics should not be None"

            analytics = result['analytics']
            print(f"\n📊 Analytics metadata received:")
            print(f"   - Source: {analytics.get('source_type')} ({analytics.get('platform')})")
            print(f"   - Method: {analytics.get('extraction_method')}")
            print(f"   - Frames: {analytics.get('frames_used')}")
            print(f"   - Cost: ${analytics.get('cost_breakdown', {}).get('total', 0):.4f}")

            # Verify analytics structure for videos
            assert analytics['source_type'] == 'video'
            assert analytics['platform'] in ['tiktok', 'instagram', 'youtube']
            assert analytics['extraction_method'] in ['audio_only', 'hybrid', 'vision_only']
            assert 'cost_breakdown' in analytics
            assert 'total' in analytics['cost_breakdown']

            # Step 2: Verify analytics endpoint has cost data
            print("\n📊 Step 2: Checking analytics...")
            analytics_response = await client.get("/api/v1/analytics/costs")

            assert analytics_response.status_code == 200
            analytics = analytics_response.json()

            print(f"✅ Analytics data:")
            print(f"   - Total cost: ${analytics['totals']['total']:.4f}")
            print(f"   - Videos processed: {analytics['totals']['count']}")
            print(f"   - Avg cost/video: ${analytics['avg_cost_per_video']:.4f}")

            # Verify cost tracking is working
            assert analytics['totals']['count'] > 0, "No cost records found"
            assert analytics['totals']['total'] > 0, "Total cost should be > 0"

            # Step 3: Check cost breakdown by method
            print("\n💰 Step 3: Cost breakdown by method:")
            if analytics['by_method']:
                for method, data in analytics['by_method'].items():
                    print(f"   - {method}: ${data['avg_cost']:.4f} avg ({data['count']} videos)")

            # Step 4: Verify analytics summary
            print("\n📈 Step 4: Checking summary...")
            summary_response = await client.get("/api/v1/analytics/costs/summary")

            assert summary_response.status_code == 200
            summary = summary_response.json()

            print(f"✅ Summary:")
            print(f"   - Today: ${summary['today']['cost']:.2f} ({summary['today']['count']} videos)")
            print(f"   - This week: ${summary['this_week']['cost']:.2f} ({summary['this_week']['count']} videos)")
            print(f"   - Avg/video: ${summary['avg_per_video']:.4f}")

            # Step 5: Verify analytics health
            print("\n🏥 Step 5: Checking analytics health...")
            health_response = await client.get("/api/v1/analytics/health")

            assert health_response.status_code == 200
            health = health_response.json()

            print(f"✅ Health check:")
            print(f"   - Status: {health['status']}")
            print(f"   - Records: {health['records_count']}")
            if health['records_count'] > 0:
                print(f"   - Oldest: {health['oldest_record']}")
                print(f"   - Newest: {health['newest_record']}")

            assert health['status'] == 'healthy'
            assert health['records_count'] > 0

    async def test_analytics_endpoints_structure(self):
        """
        Test that analytics endpoints return correct structure (no URL needed).
        """
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Test /analytics/costs
            response = await client.get("/api/v1/analytics/costs")
            assert response.status_code == 200

            data = response.json()
            assert 'period' in data
            assert 'totals' in data
            assert 'by_method' in data
            assert 'by_platform' in data
            assert 'trends' in data
            assert 'avg_cost_per_video' in data

            # Test /analytics/costs/summary
            summary_response = await client.get("/api/v1/analytics/costs/summary")
            assert summary_response.status_code == 200

            summary = summary_response.json()
            assert 'today' in summary
            assert 'this_week' in summary
            assert 'this_month' in summary
            assert 'avg_per_video' in summary
            assert 'method_distribution' in summary

            # Test /analytics/health
            health_response = await client.get("/api/v1/analytics/health")
            assert health_response.status_code == 200

            health = health_response.json()
            assert 'status' in health
            assert 'records_count' in health

    async def test_analytics_filtering(self, tiktok_url):
        """
        Test analytics filtering by platform and date range.
        """
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # First ingest a video to have data
            await client.post(
                "/api/v1/ingest",
                json={"url": tiktok_url, "generate_image": False}
            )

            # Test platform filtering
            response = await client.get("/api/v1/analytics/costs?platform=tiktok")
            assert response.status_code == 200

            data = response.json()
            assert 'by_platform' in data

            # If we have TikTok data, it should appear
            if data['totals']['count'] > 0:
                assert 'tiktok' in data['by_platform'] or len(data['by_platform']) == 0
