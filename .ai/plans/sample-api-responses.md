# Sample API Responses for Ingestion Endpoint

This document provides sample responses from the `/api/v1/ingest` endpoint for the backend team to use when implementing analytics storage.

## Important: User Import Tracking

The `/api/v1/ingest` endpoint now accepts an optional `user_id` parameter:

```json
{
  "url": "https://www.tiktok.com/@user/video/123",
  "generate_image": false,
  "user_id": "d2kceippeops73cbrkq0"  // Optional: ID of user importing the recipe
}
```

**When `user_id` is provided:**
- The recipe will be created with `user_created: true`
- The `created_by_user_id` will be set to the provided user ID
- The `imported_from_url` will be set to the original URL
- The recipe will appear in the user's "My Recipes" collection

**When `user_id` is NOT provided (or null):**
- The recipe will be created with `user_created: false`
- The `created_by_user_id` will be null
- The `imported_from_url` will be null
- The recipe will only appear in the global recipe library (not user-specific)

## 1. Successful Video Ingestion (TikTok - Vision Only)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789",
  "generate_image": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "recipe_id": "550e8400-e29b-41d4-a716-446655440000",
  "recipe_name": "Garlic Herb Tortilla",
  "ingredients_processed": 4,
  "image_generated": false,
  "processing_time_seconds": 45.2,
  "source_type": "video",
  "analytics": {
    "url": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789",
    "source_type": "video",
    "platform": "tiktok",
    "extraction_method": "vision_only",
    "frames_used": 5,
    "audio_duration_seconds": 0.0,
    "video_size_mb": 8.2,
    "processing_time_ms": 37810,
    "transcript_tokens": 0,
    "output_tokens": 487,
    "confidence_score": null,
    "fallback_reason": null,
    "cost_breakdown": {
      "whisper_transcription": 0.0,
      "gpt4_text": 0.00487,
      "gpt4_vision": 0.15,
      "video_download": 0.00082,
      "total": 0.15569
    }
  }
}
```

---

## 2. Successful Video Ingestion (Instagram - Hybrid Mode)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.instagram.com/reel/ABC123xyz/",
  "generate_image": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "recipe_id": "660e8400-e29b-41d4-a716-446655440111",
  "recipe_name": "Quick Pasta Carbonara",
  "ingredients_processed": 8,
  "image_generated": true,
  "processing_time_seconds": 52.8,
  "source_type": "video",
  "analytics": {
    "url": "https://www.instagram.com/reel/ABC123xyz/",
    "source_type": "video",
    "platform": "instagram",
    "extraction_method": "hybrid",
    "frames_used": 3,
    "audio_duration_seconds": 58.5,
    "video_size_mb": 12.4,
    "processing_time_ms": 42340,
    "transcript_tokens": 245,
    "output_tokens": 512,
    "confidence_score": 0.65,
    "fallback_reason": null,
    "cost_breakdown": {
      "whisper_transcription": 0.006,
      "gpt4_text": 0.0075,
      "gpt4_vision": 0.09,
      "video_download": 0.00124,
      "total": 0.10474
    }
  }
}
```

---

## 3. Successful Video Ingestion (YouTube - Audio Only)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.youtube.com/shorts/AbCdEfG123",
  "generate_image": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "recipe_id": "770e8400-e29b-41d4-a716-446655440222",
  "recipe_name": "Easy Chocolate Chip Cookies",
  "ingredients_processed": 10,
  "image_generated": false,
  "processing_time_seconds": 28.3,
  "source_type": "video",
  "analytics": {
    "url": "https://www.youtube.com/shorts/AbCdEfG123",
    "source_type": "video",
    "platform": "youtube",
    "extraction_method": "audio_only",
    "frames_used": 0,
    "audio_duration_seconds": 45.2,
    "video_size_mb": 6.8,
    "processing_time_ms": 24120,
    "transcript_tokens": 312,
    "output_tokens": 428,
    "confidence_score": 0.85,
    "fallback_reason": null,
    "cost_breakdown": {
      "whisper_transcription": 0.00452,
      "gpt4_text": 0.0074,
      "gpt4_vision": 0.0,
      "video_download": 0.00068,
      "total": 0.0126
    }
  }
}
```

---

## 4. Successful Website Ingestion (AllRecipes)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
  "generate_image": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "recipe_id": "880e8400-e29b-41d4-a716-446655440333",
  "recipe_name": "Best Chocolate Chip Cookies",
  "ingredients_processed": 12,
  "image_generated": true,
  "processing_time_seconds": 18.7,
  "source_type": "website",
  "analytics": {
    "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
    "source_type": "website",
    "platform": "allrecipes",
    "extraction_method": null,
    "frames_used": 0,
    "audio_duration_seconds": null,
    "video_size_mb": null,
    "processing_time_ms": 18700,
    "transcript_tokens": 0,
    "output_tokens": 0,
    "confidence_score": null,
    "fallback_reason": null,
    "cost_breakdown": {
      "spoonacular_api": 0.0,
      "gpt4_text": 0.0,
      "total": 0.0
    }
  }
}
```

---

## 5. Successful Website Ingestion (FoodNetwork)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.foodnetwork.com/recipes/alton-brown/guacamole-recipe-1940609",
  "generate_image": false
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "recipe_id": "990e8400-e29b-41d4-a716-446655440444",
  "recipe_name": "Perfect Guacamole",
  "ingredients_processed": 6,
  "image_generated": false,
  "processing_time_seconds": 14.2,
  "source_type": "website",
  "analytics": {
    "url": "https://www.foodnetwork.com/recipes/alton-brown/guacamole-recipe-1940609",
    "source_type": "website",
    "platform": "foodnetwork",
    "extraction_method": null,
    "frames_used": 0,
    "audio_duration_seconds": null,
    "video_size_mb": null,
    "processing_time_ms": 14200,
    "transcript_tokens": 0,
    "output_tokens": 0,
    "confidence_score": null,
    "fallback_reason": null,
    "cost_breakdown": {
      "spoonacular_api": 0.0,
      "gpt4_text": 0.0,
      "total": 0.0
    }
  }
}
```

---

## 6. Error Response - Video Download Failed

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.tiktok.com/@user/video/999999999999",
  "generate_image": false
}
```

**Response (400 Bad Request):**
```json
{
  "detail": {
    "success": false,
    "error_code": "DOWNLOAD_FAILED",
    "error_message": "Failed to download video: [TikTok] Unable to extract video data. Video may be private, deleted, or region-restricted.",
    "processing_time_seconds": 8.5
  }
}
```

---

## 7. Error Response - Video Parse Failed (Not a Recipe)

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.tiktok.com/@dancer/video/7234567890987654321",
  "generate_image": false
}
```

**Response (400 Bad Request):**
```json
{
  "detail": {
    "success": false,
    "error_code": "NOT_A_RECIPE",
    "error_message": "Video does not contain a recipe. GPT-4 could not extract recipe information from the video content.",
    "processing_time_seconds": 35.2
  }
}
```

---

## 8. Error Response - Website Scraping Failed

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.randomwebsite.com/some-page",
  "generate_image": false
}
```

**Response (500 Internal Server Error):**
```json
{
  "detail": {
    "success": false,
    "error_code": "INGESTION_FAILED",
    "error_message": "Failed to scrape recipe: Could not find recipe on page. The website may not be supported or the page does not contain a recipe.",
    "processing_time_seconds": 12.3
  }
}
```

---

## 9. Error Response - Ingredient Processing Failed

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.instagram.com/reel/XYZ789abc/",
  "generate_image": false
}
```

**Response (500 Internal Server Error):**
```json
{
  "detail": {
    "success": false,
    "error_code": "INGESTION_FAILED",
    "error_message": "Failed to process ingredients: Could not parse ingredient '??? cup of mystery powder'. Please check the recipe content.",
    "processing_time_seconds": 28.7
  }
}
```

---

## 10. Error Response - eKitchen API Unavailable

**Request:**
```json
POST /api/v1/ingest
{
  "url": "https://www.tiktok.com/@cookingwithshereen/video/7234567890123456789",
  "generate_image": false
}
```

**Response (503 Service Unavailable):**
```json
{
  "error": "Service unavailable - eKitchen authentication failed on startup",
  "detail": "HTTP 503: Service Unavailable",
  "hint": "Check EKITCHEN_BASE_URL, EKITCHEN_ADMIN_EMAIL, EKITCHEN_ADMIN_PASSWORD environment variables"
}
```

---

## Analytics Field Specifications

### Video Ingestion Analytics (source_type: "video")

| Field | Type | Description | Can be NULL? | Example Values |
|-------|------|-------------|--------------|----------------|
| `url` | string | Original video URL | No | `"https://www.tiktok.com/@user/video/123"` |
| `source_type` | string | Always "video" for videos | No | `"video"` |
| `platform` | string | Video platform | No | `"tiktok"`, `"instagram"`, `"youtube"` |
| `extraction_method` | string | How recipe was extracted | No | `"audio_only"`, `"hybrid"`, `"vision_only"` |
| `frames_used` | integer | Number of video frames analyzed | No | `0` (audio_only), `3` (hybrid), `5` (vision_only) |
| `audio_duration_seconds` | float | Length of audio in seconds | Yes | `45.2` or `null` (vision_only) |
| `video_size_mb` | float | Video file size in MB | Yes | `8.2` |
| `processing_time_ms` | integer | Total processing time in milliseconds | Yes | `37810` |
| `transcript_tokens` | integer | Whisper API token count | Yes | `312` or `0` (vision_only) |
| `output_tokens` | integer | GPT-4 output token count | Yes | `487` |
| `confidence_score` | float | Audio transcription confidence (0.0-1.0) | Yes | `0.85` or `null` |
| `fallback_reason` | string | Why fallback occurred | Yes | `"Low audio confidence"` or `null` |
| `cost_breakdown` | object | Detailed cost breakdown | No | See below |

### Website Ingestion Analytics (source_type: "website")

| Field | Type | Description | Can be NULL? | Example Values |
|-------|------|-------------|--------------|----------------|
| `url` | string | Original website URL | No | `"https://www.allrecipes.com/recipe/123/"` |
| `source_type` | string | Always "website" for websites | No | `"website"` |
| `platform` | string | Website domain name | No | `"allrecipes"`, `"foodnetwork"`, `"bonappetit"` |
| `extraction_method` | string | NULL for websites (not applicable) | Yes | `null` |
| `frames_used` | integer | Always 0 for websites | No | `0` |
| `audio_duration_seconds` | float | NULL for websites (not applicable) | Yes | `null` |
| `video_size_mb` | float | NULL for websites (not applicable) | Yes | `null` |
| `processing_time_ms` | integer | Total processing time in milliseconds | Yes | `18700` |
| `transcript_tokens` | integer | Always 0 for websites | No | `0` |
| `output_tokens` | integer | Always 0 for websites (could track GPT-4 usage in future) | No | `0` |
| `confidence_score` | float | NULL for websites (not applicable) | Yes | `null` |
| `fallback_reason` | string | NULL for websites (not applicable) | Yes | `null` |
| `cost_breakdown` | object | Detailed cost breakdown | No | See below |

### Cost Breakdown Structure

#### For Videos:
```json
{
  "whisper_transcription": 0.006,      // Whisper API cost ($0.006/minute)
  "gpt4_text": 0.0075,                  // GPT-4 text API cost
  "gpt4_vision": 0.09,                  // GPT-4 Vision API cost (~$0.03/image)
  "video_download": 0.00124,            // Bandwidth cost (~$0.0001/MB)
  "total": 0.10474                      // Sum of all costs
}
```

#### For Websites:
```json
{
  "spoonacular_api": 0.0,               // Spoonacular API cost (if used)
  "gpt4_text": 0.0,                     // GPT-4 cost for ingredient parsing (if used)
  "total": 0.0                          // Sum of all costs
}
```

**Note**: Website costs are currently tracked as `0.0` because:
- recipe-scrapers library is free (no API costs)
- Spoonacular enrichment is optional and not always used
- GPT-4 ingredient parsing costs could be tracked in future if needed

---

## Implementation Notes for Backend Team

### 1. Analytics Field is Always Present in Success Responses
When `success: true`, the `analytics` field will **always** be present and **never null**.

### 2. Video-Specific Fields are NULL for Websites
When storing website ingestion analytics:
- `extraction_method` → NULL
- `audio_duration_seconds` → NULL
- `video_size_mb` → NULL
- `confidence_score` → NULL
- `fallback_reason` → NULL

### 3. Error Responses Do NOT Include Analytics
When ingestion fails, the response will have:
- `detail.success: false`
- `detail.error_code: string`
- `detail.error_message: string`
- `detail.processing_time_seconds: float`
- **NO `analytics` field**

### 4. Platform Name Extraction
For websites, the platform name is extracted from the URL:
- `"https://www.allrecipes.com/..."` → `"allrecipes"`
- `"https://www.foodnetwork.com/..."` → `"foodnetwork"`
- `"https://bonappetit.com/..."` → `"bonappetit"`

Logic: Remove `www.`, split by `.`, take first part.

### 5. Cost Breakdown JSONB Storage
Store the entire `cost_breakdown` object as JSONB in PostgreSQL:
```sql
cost_breakdown JSONB NOT NULL
```

This allows flexible querying:
```sql
-- Get total cost
SELECT (cost_breakdown->>'total')::decimal FROM ingestion_analytics;

-- Get Whisper costs only
SELECT (cost_breakdown->>'whisper_transcription')::decimal FROM ingestion_analytics WHERE extraction_method = 'audio_only';
```

### 6. Recommended Validation on Backend
```ruby
# Only validate video-specific fields for videos
validates :extraction_method,
  inclusion: { in: %w[audio_only hybrid vision_only] },
  if: -> { source_type == 'video' }

# Ensure video-specific fields are NULL for websites
validates :extraction_method,
  absence: true,
  if: -> { source_type == 'website' }
```

### 7. Example Backend Storage Code (Ruby/Rails)
```ruby
if response[:success] && response[:analytics].present?
  IngestionAnalytic.create!(
    recipe_id: recipe.id,
    url: response[:analytics][:url],
    source_type: response[:analytics][:source_type],
    platform: response[:analytics][:platform],
    extraction_method: response[:analytics][:extraction_method], # NULL for websites
    frames_used: response[:analytics][:frames_used] || 0,
    audio_duration_seconds: response[:analytics][:audio_duration_seconds],
    video_size_mb: response[:analytics][:video_size_mb],
    processing_time_ms: response[:analytics][:processing_time_ms],
    transcript_tokens: response[:analytics][:transcript_tokens] || 0,
    output_tokens: response[:analytics][:output_tokens] || 0,
    confidence_score: response[:analytics][:confidence_score],
    fallback_reason: response[:analytics][:fallback_reason],
    cost_breakdown: response[:analytics][:cost_breakdown] # JSONB
  )
end
```

---

## Testing Checklist for Backend

- [ ] Successfully stores video analytics with all fields populated
- [ ] Successfully stores website analytics with NULL video-specific fields
- [ ] JSONB cost_breakdown can be queried (e.g., `WHERE (cost_breakdown->>'total')::decimal > 0.10`)
- [ ] Can aggregate costs by extraction_method
- [ ] Can aggregate costs by platform
- [ ] Can filter by source_type ('video' vs 'website')
- [ ] Handles NULL values correctly (audio_duration_seconds, confidence_score, etc.)
- [ ] Foreign key constraint works (recipe_id references global_recipes)
- [ ] Cascade delete works (deleting recipe deletes analytics)
- [ ] Indexes improve query performance (idx_source_type, idx_platform, etc.)
