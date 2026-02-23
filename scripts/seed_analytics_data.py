"""
Seed analytics data for testing the dashboard.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.routers.analytics import record_extraction_cost
from datetime import datetime, timedelta

print("📥 Seeding analytics data for dashboard testing...\n")

# Simulate a week of data
base_time = datetime.now()

# Day 1-2: Audio-only (cheap)
for i in range(5):
    record_extraction_cost({
        'url': f'https://www.tiktok.com/@user/video/{i}',
        'platform': 'tiktok',
        'extraction_method': 'audio_only',
        'cost_breakdown': {
            'whisper_transcription': 0.006,
            'gpt4_text': 0.0055,
            'gpt4_vision': 0.0,
            'video_download': 0.0005,
            'total': 0.012
        },
        'frames_used': 0,
        'audio_duration_seconds': 60,
        'processing_time_ms': 5000,
        'success': True
    })
    print(f"✅ Added audio-only TikTok video #{i+1}")

# Day 3-4: Hybrid (medium)
for i in range(3):
    record_extraction_cost({
        'url': f'https://www.instagram.com/reel/{i}',
        'platform': 'instagram',
        'extraction_method': 'hybrid',
        'cost_breakdown': {
            'whisper_transcription': 0.0045,
            'gpt4_text': 0.0054,
            'gpt4_vision': 0.09,
            'video_download': 0.0008,
            'total': 0.1007
        },
        'frames_used': 3,
        'audio_duration_seconds': 45,
        'processing_time_ms': 12000,
        'success': True
    })
    print(f"✅ Added hybrid Instagram reel #{i+1}")

# Day 5-7: Vision-only (expensive)
for i in range(2):
    record_extraction_cost({
        'url': f'https://www.youtube.com/shorts/{i}',
        'platform': 'youtube',
        'extraction_method': 'vision_only',
        'cost_breakdown': {
            'whisper_transcription': 0.0,
            'gpt4_text': 0.0,
            'gpt4_vision': 0.15,
            'video_download': 0.0012,
            'total': 0.1512
        },
        'frames_used': 5,
        'audio_duration_seconds': 0,
        'processing_time_ms': 15000,
        'success': True
    })
    print(f"✅ Added vision-only YouTube short #{i+1}")

print(f"\n✅ Seeded 10 analytics records successfully!")
print(f"📊 Total cost: $0.6645")
print(f"\n🚀 Now visit: http://localhost:8000/dashboard")
