# GSD Plan: TikWM Integration + Description-First Pipeline

## Goal
Fix TikTok ingestion (blocked by IP bans) and make the pipeline smarter by checking video descriptions before expensive audio/vision processing.

---

## Phase 1: TikWM as Primary TikTok Download Method
**Priority**: P0 | **Effort**: Medium | **Risk**: Low

### Problem
TikTok blocks datacenter IPs (Railway/GCP). yt-dlp fails with "Your IP address is blocked." TikWM API works from any IP, is free (5,000 req/day), returns video URLs + full video metadata including description text.

### Architecture Change

**Current flow:**
```
TikTok URL → yt-dlp download → Whisper transcribe → GPT-4 parse → recipe
```

**New flow:**
```
TikTok URL → TikWM API (metadata + download URLs)
  → Step A: Check description for full recipe
    → If has ingredients + steps: GPT-4 parse description → recipe (SKIP download/transcribe)
    → If partial or no recipe info: continue to Step B
  → Step B: Download video via TikWM CDN URL → existing audio/vision pipeline → recipe
```

### Task 1: Add TikWM client method

**File**: `parsers/video.py`

Add `_fetch_tiktok_metadata_via_tikwm(url)` method:
- POST/GET to `https://www.tikwm.com/api/?url={url}`
- Return dict with: `title`, `description`, `video_url` (play field), `audio_url` (music field), `duration`, `author`
- Handle errors gracefully (TikWM down, video deleted, rate limit)
- Log TikWM response time and status

**API contract** (confirmed working):
```python
GET https://www.tikwm.com/api/?url={tiktok_url}
Response: {
  "code": 0,  # 0 = success, -1 = error
  "data": {
    "id": "video_id",
    "title": "full description text with recipe...",
    "play": "https://v16m.tiktokcdn-us.com/...",  # video download URL
    "music": "https://v16-ies-music.tiktokcdn-us.com/...",  # audio URL
    "duration": 64,
    "author": { "nickname": "..." }
  }
}
```

### Task 2: Replace yt-dlp with TikWM for TikTok downloads

**File**: `parsers/video.py` — modify `parse()` method and download methods

In the `parse()` method, after platform detection:
1. If platform == 'tiktok': call `_fetch_tiktok_metadata_via_tikwm(url)`
2. Use the returned video/audio URLs for download (plain HTTP GET, no yt-dlp)
3. If TikWM fails: return error (no yt-dlp fallback — TikWM is the only TikTok method)
4. For Instagram/YouTube: continue using yt-dlp as before

Add `_download_from_url(url, output_path)` helper that does a simple `requests.get()` to download from CDN URLs returned by TikWM.

**Remove**: All yt-dlp TikTok-specific logic. yt-dlp is only for Instagram/YouTube now.

### Verification
- Run ingestion with the test TikTok URL from Railway
- Video downloads successfully via TikWM CDN URL
- Recipe is extracted correctly
- yt-dlp is NOT called for TikTok URLs (check logs)

---

## Phase 2: Description-First Analysis
**Priority**: P0 | **Effort**: Medium | **Risk**: Low

### Problem
We currently always download video → transcribe → parse, even when the TikTok/Instagram description already contains the full recipe. This wastes time and API credits (Whisper + GPT-4 vision). Many recipe creators paste the full recipe in the description.

### Architecture

**New step inserted before download:**
```
metadata (title + description)
  → GPT-4 analysis: "Is this a recipe? Does description have ingredients + steps?"
  → Response: { is_recipe: bool, has_full_recipe: bool, recipe_data?: {...} }

If has_full_recipe:
  → Parse recipe from description text → DONE (no video download needed)
  → Cost: ~$0.001 (text-only GPT-4 call)

If is_recipe but NOT has_full_recipe:
  → Continue with video download + audio/vision pipeline
  → Cost: $0.01-0.05 (full pipeline)

If NOT is_recipe:
  → Early reject: "This video doesn't appear to be a recipe"
  → Cost: ~$0.001 (just the classification call)
```

### Task 3: Add description analysis method

**File**: `parsers/video.py`

Add `_analyze_description(title, description, platform)` method:
- Send title + description to GPT-4 with a structured prompt
- Prompt asks: (1) Is this a recipe video? (2) Does the description contain a COMPLETE recipe (ingredients with quantities AND cooking steps)?
- If complete recipe found: parse it into the standard recipe structure in the same call
- Return: `{ is_recipe: bool, has_full_recipe: bool, confidence: float, recipe_data: dict | None, rejection_reason: str | None }`

**GPT-4 prompt design:**
```
You are analyzing a video description to determine if it contains a recipe.

Title: {title}
Description: {description}
Platform: {platform}

Respond in JSON:
{
  "is_recipe": true/false,
  "has_full_recipe": true/false,  // Has BOTH ingredients with quantities AND cooking steps
  "confidence": 0.0-1.0,
  "recipe": {  // Only if has_full_recipe is true
    "name": "...",
    "ingredients": [...],
    "steps": [...],
    "prep_time_minutes": ...,
    "cook_time_minutes": ...,
    "num_servings": ...,
    "cuisine": "...",
    "difficulty": "..."
  },
  "rejection_reason": "..."  // Only if is_recipe is false
}
```

### Task 4: Wire description analysis into parse() pipeline

**File**: `parsers/video.py` — modify `parse()` method

After TikWM metadata fetch (for TikTok) or yt-dlp info fetch (for other platforms):
1. Extract title + description from metadata
2. Call `_analyze_description(title, description, platform)`
3. If `is_recipe == False` and `confidence >= 0.8`: early reject with helpful message
4. If `has_full_recipe == True` and `confidence >= 0.8`: use `recipe_data` directly, skip download/transcribe
5. Otherwise: continue with existing audio/vision pipeline

**Important**: Even if description has a partial recipe, still run the full pipeline — the audio/video might have additional details. But log that we found partial info in description for debugging.

### Task 5: Add description-first analytics tracking

Track how often each path is taken:
- `description_full_recipe` — recipe extracted from description only (cheapest)
- `description_rejected` — video rejected as non-recipe from description (cheapest)
- `audio_only` — existing audio path
- `hybrid` — existing hybrid path
- `vision_only` — existing vision path

Add to the analytics/cost tracking that already exists.

### Verification
- Test with TikTok URL that has full recipe in description → extracts without video download
- Test with TikTok URL that has no recipe info → rejects early with message
- Test with TikTok URL that has partial recipe → falls through to audio/vision pipeline
- Test with YouTube/Instagram URLs → works as before (description check still runs)
- Analytics show new extraction methods in cost breakdown

---

## Phase 3: Resilience & Edge Cases
**Priority**: P1 | **Effort**: Small | **Risk**: Low

### Task 6: Handle TikWM failure gracefully

**File**: `parsers/video.py`

- If TikWM API is down or rate limited: return clear error to user
- If TikWM returns code -1 (video deleted/private): return clear error to user
- Add timeout (5s) to TikWM API calls
- Log TikWM failures for monitoring

### Task 7: Handle description edge cases

- Very long descriptions (>4000 chars): truncate to avoid token waste
- Descriptions in non-English languages: GPT-4 handles this, but note it in the prompt
- Descriptions with just hashtags and no recipe: should be classified as `is_recipe: false`
- Descriptions with "link in bio" instead of actual recipe: should be `has_full_recipe: false`

---

## Execution Order

| Phase | Task | Dependencies | Effort |
|-------|------|-------------|--------|
| 1 | Task 1: TikWM client method | None | Small |
| 1 | Task 2: Replace yt-dlp for TikTok | Task 1 | Medium |
| 2 | Task 3: Description analysis method | None | Medium |
| 2 | Task 4: Wire into pipeline | Tasks 1, 2, 3 | Medium |
| 2 | Task 5: Analytics tracking | Task 4 | Small |
| 3 | Task 6: TikWM failure handling | Task 1 | Small |
| 3 | Task 7: Description edge cases | Task 3 | Small |

## Wave Execution

**Wave 1** (parallel): Task 1 + Task 3
**Wave 2** (sequential): Task 2 → Task 4 → Task 5
**Wave 3** (parallel): Task 6 + Task 7

## Cost Impact

| Scenario | Before | After |
|----------|--------|-------|
| TikTok with full recipe in description | $0.01-0.05 (download + Whisper + GPT-4) | ~$0.001 (GPT-4 text only) |
| TikTok with no recipe in description | $0.01-0.05 (full pipeline, wasted) | ~$0.001 (early reject) |
| TikTok needs audio/vision | $0.01-0.05 | $0.01-0.05 (same, but download via TikWM) |
| Non-TikTok platforms | No change | +$0.001 for description check (saves $ if description has recipe) |

## Success Criteria
- [ ] TikTok ingestion works from Railway (no IP block errors)
- [ ] Videos with full recipe in description skip download/transcribe
- [ ] Non-recipe videos are rejected early with clear message
- [ ] yt-dlp still works as fallback for non-TikTok platforms
- [ ] Cost per ingestion drops for description-rich videos
- [ ] Analytics track which extraction path was used
