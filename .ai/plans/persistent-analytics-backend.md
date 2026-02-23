# Persistent Analytics Storage - Backend Implementation Plan

## Context

Currently, recipe ingestion analytics (costs, extraction methods, performance metrics, source types) are stored **in-memory** in the ingestion service. This means:
- ❌ Data is lost on service restart
- ❌ Data is not accessible to eKitchen backend
- ❌ No historical analytics beyond current session
- ❌ Cannot query analytics from eKitchen admin dashboard

**Supported Sources**:
- Videos: TikTok, Instagram, YouTube Shorts
- Websites: 200+ recipe sites (AllRecipes, FoodNetwork, etc.)
- Future: PDFs, images, voice recordings

## Goal

Implement **Option 1: Return analytics in ingestion response**, where:
1. Ingestion service returns analytics metadata in the API response
2. eKitchen backend stores analytics in its PostgreSQL database
3. eKitchen can query analytics for dashboard/reporting
4. Ingestion service remains stateless (no database needed)

## Architecture Overview

```
┌─────────────────────────┐
│  Ingestion Service      │
│  (ekitchen-ingestion)   │
│                         │
│  POST /api/v1/ingest    │
│  ├─ Parse video         │
│  ├─ Calculate costs     │
│  └─ Return response ────┼────────┐
└─────────────────────────┘        │
                                   │ Response includes
                                   │ analytics metadata
                                   ▼
                        ┌──────────────────────┐
                        │  eKitchen Backend    │
                        │  (Rails/Go)          │
                        │                      │
                        │  POST /ingest        │
                        │  ├─ Call ingestion   │
                        │  ├─ Create recipe    │
                        │  └─ Store analytics ─┼──► PostgreSQL
                        └──────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Analytics Dashboard │
                        │  Query from eKitchen │
                        └──────────────────────┘
```

## Implementation Plan

### Phase 1: Update Ingestion Service Response (This Service)

#### 1.1 Update `IngestResponse` Model
**File**: `app/routers/ingest.py`

Add analytics field to response model:
```python
class IngestResponse(BaseModel):
    success: bool = True
    recipe_id: str
    recipe_name: str
    ingredients_processed: int
    image_generated: bool
    processing_time_seconds: float
    source_type: str

    # NEW: Analytics metadata
    analytics: Optional[Dict[str, Any]] = None
```

**Analytics structure**:
```json
{
  "extraction_method": "vision_only",
  "platform": "tiktok",
  "url": "https://...",
  "cost_breakdown": {
    "whisper_transcription": 0.0,
    "gpt4_text": 0.0,
    "gpt4_vision": 0.15,
    "video_download": 0.0012,
    "total": 0.1512
  },
  "frames_used": 5,
  "audio_duration_seconds": 0,
  "video_size_mb": 8.2,
  "processing_time_ms": 37810,
  "transcript_tokens": 0,
  "output_tokens": 500,
  "confidence_score": 0.85,
  "fallback_reason": null
}
```

#### 1.2 Populate Analytics in Response
**File**: `app/routers/ingest.py`

In `_ingest_video()` function, after successful ingestion:
```python
return IngestResponse(
    success=True,
    recipe_id=result.recipe_id,
    recipe_name=result.recipe_name or "Unknown",
    ingredients_processed=result.ingredients_processed,
    image_generated=result.image_generated,
    processing_time_seconds=processing_time,
    source_type="video",
    # NEW: Add analytics from ParseResult
    analytics={
        "extraction_method": parse_result.extraction_method,
        "platform": platform,
        "url": url,
        "cost_breakdown": parse_result.cost_breakdown,
        "frames_used": parse_result.frames_used,
        "audio_duration_seconds": parse_result.audio_duration_seconds,
        "video_size_mb": parse_result.video_size_mb,
        "processing_time_ms": parse_result.processing_time_ms,
        "transcript_tokens": parse_result.transcript_tokens,
        "output_tokens": parse_result.output_tokens,
        "confidence_score": parse_result.confidence_score,
        "fallback_reason": parse_result.fallback_reason,
    }
)
```

#### 1.3 Keep In-Memory Analytics (Optional, for backward compatibility)
**File**: `app/routers/ingest.py`

Keep the existing `record_extraction_cost()` call for:
- Development/testing with local dashboard
- Real-time monitoring without database
- Temporary analytics until eKitchen stores them

This is **optional** - can be removed once eKitchen backend is ready.

#### 1.4 Update API Documentation
**File**: `app/routers/ingest.py`

Update the docstring for `/ingest` endpoint to document the new `analytics` field in the response.

---

### Phase 2: eKitchen Backend Changes (Backend Agent's Work)

#### 2.1 Create Database Migration
**Target**: eKitchen backend repository

Create new table `ingestion_analytics` (universal for all source types):
```sql
CREATE TABLE ingestion_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recipe_id UUID NOT NULL REFERENCES global_recipes(id) ON DELETE CASCADE,

  -- Source metadata
  url TEXT NOT NULL,
  source_type VARCHAR(50) NOT NULL, -- 'video' or 'website'
  platform VARCHAR(50), -- For videos: 'tiktok', 'instagram', 'youtube'. For websites: 'allrecipes', 'foodnetwork', etc.

  -- Video-specific extraction details (NULL for websites)
  extraction_method VARCHAR(50), -- 'audio_only', 'hybrid', 'vision_only' (videos only)
  frames_used INTEGER DEFAULT 0,
  audio_duration_seconds DECIMAL(10, 2),
  video_size_mb DECIMAL(10, 2),

  -- Universal fields (applies to both videos and websites)
  processing_time_ms INTEGER,
  transcript_tokens INTEGER DEFAULT 0, -- Whisper tokens for videos, or scraper-extracted text for websites
  output_tokens INTEGER DEFAULT 0, -- GPT tokens for recipe extraction

  -- Quality metrics
  confidence_score DECIMAL(5, 4),
  fallback_reason TEXT,

  -- Cost breakdown (JSONB for flexibility)
  cost_breakdown JSONB NOT NULL,
  -- Video example: {"whisper_transcription": 0.006, "gpt4_text": 0.0055, "gpt4_vision": 0.09, "total": 0.1015}
  -- Website example: {"gpt4_text": 0.002, "spoonacular_api": 0.001, "total": 0.003}

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),

  -- Indexes for common queries
  INDEX idx_source_type (source_type),
  INDEX idx_platform (platform),
  INDEX idx_extraction_method (extraction_method),
  INDEX idx_created_at (created_at),
  INDEX idx_recipe_id (recipe_id)
);

-- Add comment for documentation
COMMENT ON TABLE ingestion_analytics IS 'Analytics data for all recipe ingestion (videos, websites, etc.) including costs, extraction methods, and performance metrics';
```

**Migration file naming**: `YYYYMMDDHHMMSS_create_ingestion_analytics.sql` (or Rails migration format)

#### 2.2 Update Ingestion Handler
**Target**: eKitchen backend ingestion controller/handler

When calling ingestion service, capture and store analytics:

```ruby
# Example for Rails
def ingest_video_recipe
  # Call ingestion service
  response = IngestionService.ingest_video(params[:url])

  if response[:success]
    # Create recipe (existing logic)
    recipe = create_recipe(response[:data])

    # NEW: Store analytics
    if response[:analytics].present?
      IngestionAnalytic.create!(
        recipe_id: recipe.id,
        url: response[:analytics][:url],
        source_type: response[:source_type], # 'video' or 'website'
        platform: response[:analytics][:platform],
        extraction_method: response[:analytics][:extraction_method], # NULL for websites
        frames_used: response[:analytics][:frames_used] || 0,
        audio_duration_seconds: response[:analytics][:audio_duration_seconds],
        video_size_mb: response[:analytics][:video_size_mb],
        processing_time_ms: response[:analytics][:processing_time_ms],
        transcript_tokens: response[:analytics][:transcript_tokens],
        output_tokens: response[:analytics][:output_tokens],
        confidence_score: response[:analytics][:confidence_score],
        fallback_reason: response[:analytics][:fallback_reason],
        cost_breakdown: response[:analytics][:cost_breakdown] # JSONB
      )
    end

    render json: { success: true, recipe_id: recipe.id }
  else
    render json: { success: false, error: response[:error] }, status: :unprocessable_entity
  end
end
```

#### 2.3 Create Model
**Target**: eKitchen backend models

```ruby
# app/models/ingestion_analytic.rb
class IngestionAnalytic < ApplicationRecord
  belongs_to :global_recipe, foreign_key: :recipe_id

  validates :url, presence: true
  validates :source_type, inclusion: { in: %w[video website] }
  validates :cost_breakdown, presence: true

  # Video-specific validations (only for videos)
  validates :extraction_method,
    inclusion: { in: %w[audio_only hybrid vision_only] },
    if: -> { source_type == 'video' }

  # Scopes for common queries
  scope :videos, -> { where(source_type: 'video') }
  scope :websites, -> { where(source_type: 'website') }
  scope :by_source_type, ->(type) { where(source_type: type) }
  scope :by_platform, ->(platform) { where(platform: platform) }
  scope :by_method, ->(method) { where(extraction_method: method) }
  scope :recent, -> { order(created_at: :desc) }
  scope :today, -> { where('created_at >= ?', Time.current.beginning_of_day) }
  scope :this_week, -> { where('created_at >= ?', 7.days.ago) }
  scope :this_month, -> { where('created_at >= ?', 30.days.ago) }

  # Helper methods
  def total_cost
    cost_breakdown['total'] || 0
  end

  def self.total_spent
    sum("(cost_breakdown->>'total')::decimal")
  end

  def self.average_cost
    avg("(cost_breakdown->>'total')::decimal")
  end
end
```

#### 2.4 Create Analytics API Endpoints
**Target**: eKitchen backend API

Create endpoints to query analytics:

```ruby
# config/routes.rb
namespace :api do
  namespace :v1 do
    namespace :analytics do
      get 'ingestion/summary', to: 'ingestion#summary'
      get 'ingestion/costs', to: 'ingestion#costs'
      get 'ingestion/by_source_type', to: 'ingestion#by_source_type'
      get 'ingestion/by_method', to: 'ingestion#by_method'
      get 'ingestion/by_platform', to: 'ingestion#by_platform'
      get 'ingestion/daily_trend', to: 'ingestion#daily_trend'
    end
  end
end

# app/controllers/api/v1/analytics/ingestion_controller.rb
class Api::V1::Analytics::IngestionController < ApplicationController
  def summary
    render json: {
      total_cost: IngestionAnalytic.total_spent,
      total_recipes: IngestionAnalytic.count,
      avg_cost: IngestionAnalytic.average_cost,
      by_source: {
        videos: IngestionAnalytic.videos.count,
        websites: IngestionAnalytic.websites.count
      },
      today: {
        cost: IngestionAnalytic.today.total_spent,
        count: IngestionAnalytic.today.count
      },
      this_week: {
        cost: IngestionAnalytic.this_week.total_spent,
        count: IngestionAnalytic.this_week.count
      }
    }
  end

  def costs
    # Similar to ingestion service's /analytics/costs endpoint
    analytics = IngestionAnalytic.all

    # Aggregate by source_type, method, platform, etc.
    # Return same format as ingestion service for dashboard compatibility
  end

  def by_source_type
    render json: {
      videos: {
        count: IngestionAnalytic.videos.count,
        total_cost: IngestionAnalytic.videos.total_spent,
        avg_cost: IngestionAnalytic.videos.average_cost
      },
      websites: {
        count: IngestionAnalytic.websites.count,
        total_cost: IngestionAnalytic.websites.total_spent,
        avg_cost: IngestionAnalytic.websites.average_cost
      }
    }
  end

  # ... other endpoints
end
```

#### 2.5 Update Dashboard to Use eKitchen API (Optional)
**Target**: eKitchen admin dashboard or standalone analytics dashboard

Update the dashboard JavaScript to query eKitchen backend instead of ingestion service:
```javascript
// Change from:
const API_BASE = '/api/v1';

// To:
const API_BASE = 'https://ekitchen-api.example.com/api/v1/analytics/video_ingestion';
```

---

## Benefits of This Approach

✅ **Stateless Ingestion Service**: No database needed, remains lightweight
✅ **Single Source of Truth**: eKitchen owns all recipe + analytics data
✅ **Persistent Analytics**: Data survives service restarts
✅ **Historical Analysis**: Can query analytics over time
✅ **Scalable**: eKitchen can aggregate analytics from multiple ingestion instances
✅ **Backward Compatible**: In-memory analytics still work for dev/testing
✅ **Flexible Querying**: JSONB allows complex cost queries without schema changes

## Testing Strategy

### Ingestion Service Tests
1. **Unit test**: Verify `IngestResponse` includes analytics field
2. **Integration test**: Verify analytics populated correctly from `ParseResult`
3. **Smoke test**: Existing smoke test should see new `analytics` field in response

### eKitchen Backend Tests
1. **Migration test**: Verify table created with correct schema
2. **Model test**: Verify validations and associations
3. **Integration test**: Verify analytics stored when ingesting video
4. **API test**: Verify analytics endpoints return correct aggregations

## Rollout Plan

1. **Phase 1** (This PR): Update ingestion service response
   - Add `analytics` field to `IngestResponse`
   - Populate from `ParseResult`
   - Keep in-memory analytics for now (backward compatible)
   - Update API docs

2. **Phase 2** (Backend team): eKitchen backend changes
   - Create database migration
   - Update ingestion handler to store analytics
   - Create model and validations
   - Create analytics API endpoints
   - Test with staging environment

3. **Phase 3** (Optional): Dashboard migration
   - Update dashboard to query eKitchen API
   - Remove in-memory analytics from ingestion service
   - Deploy to production

## Questions for Backend Agent

1. **eKitchen stack**: Rails, Go, or other? (Affects code examples)
2. **Migration format**: Rails migrations, raw SQL, or other?
3. **Authentication**: Do analytics endpoints need auth? (Probably yes - admin only)
4. **Existing recipe model**: What's the table name? `global_recipes` or `recipes`?
5. **Naming conventions**: Snake_case or camelCase for JSON responses?
6. **Deployment**: How to coordinate deployment of both services?

## Files to Modify (Ingestion Service)

- `app/routers/ingest.py` - Add analytics to response
- `tests/test_smoke_video_ingestion.py` - Verify analytics in response
- API documentation (auto-generated from Pydantic models)

## Files to Create/Modify (eKitchen Backend)

- Database migration file
- `app/models/video_ingestion_analytic.rb` (or equivalent)
- `app/controllers/api/v1/analytics/video_ingestion_controller.rb` (or equivalent)
- Route configuration
- Tests for model, controller, integration

## Success Criteria

✅ Ingestion response includes complete analytics metadata
✅ eKitchen stores analytics in PostgreSQL
✅ Analytics persist across restarts
✅ Can query analytics via eKitchen API
✅ Dashboard shows historical data
✅ No performance degradation in ingestion flow
✅ Backward compatible with existing clients

## Timeline Estimate

- **Phase 1** (Ingestion service): 1-2 hours
- **Phase 2** (eKitchen backend): 4-6 hours
- **Phase 3** (Dashboard migration): 1-2 hours

**Total**: ~1 day of work
