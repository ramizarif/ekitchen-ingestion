# eKitchen Recipe Parser API - Quick Start Guide

## 🚀 Your API is Ready!

The recipe parser API is now running and can parse recipes from 200+ websites!

---

## ✅ What's Working

### Website Parser
✅ **200+ recipe sites supported** via recipe-scrapers
✅ **Structured JSON output** ready for Go backend
✅ **Automatic data extraction**: ingredients, steps, timing, servings, images
✅ **Confidence scoring**: 0.0-1.0 quality indicator
✅ **Smart error handling**: Categorized error codes

---

## 📡 API Endpoints

### Base URL
```
http://localhost:8000
```

### 1. Parse Recipe - `POST /api/v1/parse`

**Request:**
```bash
curl -X POST 'http://localhost:8000/api/v1/parse' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",
    "source_type": "website"
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "name": "Best Chocolate Chip Cookies",
    "description": "This classic chocolate chip cookie recipe...",
    "ingredients": [
      "1 cup butter, softened",
      "1 cup white sugar",
      "1 cup packed brown sugar",
      ...
    ],
    "steps": [
      "Gather your ingredients...",
      "Preheat the oven to 350 degrees F...",
      ...
    ],
    "servings": 48,
    "prep_time_minutes": 15,
    "cook_time_minutes": 10,
    "total_time_minutes": 25,
    "image_url": "https://...",
    "video_url": null,
    "source_metadata": {
      "author": "Dora",
      "site_name": "Allrecipes",
      "host": "allrecipes.com",
      "url": "https://..."
    }
  },
  "processing_time_ms": 431,
  "parser_used": "recipe-scrapers",
  "confidence_score": 0.9,
  "warnings": ["No timing information available"]
}
```

**Error Response (400/404/500):**
```json
{
  "detail": {
    "success": false,
    "error": {
      "code": "PARSING_FAILED",
      "message": "Error description",
      "details": "Additional context"
    },
    "processing_time_ms": 123
  }
}
```

### 2. List Parsers - `GET /api/v1/parsers`

```bash
curl http://localhost:8000/api/v1/parsers
```

**Response:**
```json
{
  "parsers": [
    {
      "source_type": "website",
      "status": "available",
      "description": "Parse recipes from 200+ websites",
      "examples": [
        "https://www.allrecipes.com/...",
        "https://www.foodnetwork.com/..."
      ]
    },
    {
      "source_type": "image",
      "status": "planned",
      "description": "Extract recipes from screenshots using GPT-4 Vision"
    }
  ]
}
```

### 3. Validate URL - `POST /api/v1/validate`

```bash
curl -X POST 'http://localhost:8000/api/v1/validate' \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://www.allrecipes.com/recipe/123/",
    "source_type": "website"
  }'
```

**Response:**
```json
{
  "valid": true,
  "source_type": "website",
  "estimated_parse_time_seconds": 3,
  "supported": true,
  "parser": "recipe-scrapers"
}
```

### 4. Health Check - `GET /health`

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-16T23:46:17.781039",
  "version": "0.1.0"
}
```

---

## 🔌 Go Service Integration

### Go HTTP Client Example

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type ParseRequest struct {
    URL        string `json:"url"`
    SourceType string `json:"source_type"`
}

type RecipeData struct {
    Name               string                 `json:"name"`
    Description        string                 `json:"description"`
    Ingredients        []string               `json:"ingredients"`
    Steps              []string               `json:"steps"`
    Servings           int                    `json:"servings"`
    PrepTimeMinutes    int                    `json:"prep_time_minutes"`
    CookTimeMinutes    int                    `json:"cook_time_minutes"`
    TotalTimeMinutes   int                    `json:"total_time_minutes"`
    ImageURL           string                 `json:"image_url"`
    VideoURL           *string                `json:"video_url"`
    SourceMetadata     map[string]interface{} `json:"source_metadata"`
}

type ParseResponse struct {
    Success          bool       `json:"success"`
    Data             RecipeData `json:"data"`
    ProcessingTimeMs int        `json:"processing_time_ms"`
    ParserUsed       string     `json:"parser_used"`
    ConfidenceScore  float64    `json:"confidence_score"`
    Warnings         []string   `json:"warnings"`
}

func ParseRecipe(url string) (*ParseResponse, error) {
    // Create request
    reqBody := ParseRequest{
        URL:        url,
        SourceType: "website",
    }

    jsonData, _ := json.Marshal(reqBody)

    // Call Python API
    client := &http.Client{Timeout: 30 * time.Second}
    resp, err := client.Post(
        "http://localhost:8000/api/v1/parse",
        "application/json",
        bytes.NewBuffer(jsonData),
    )
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    // Parse response
    var result ParseResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }

    return &result, nil
}

func main() {
    result, err := ParseRecipe("https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/")
    if err != nil {
        panic(err)
    }

    fmt.Printf("Recipe: %s\n", result.Data.Name)
    fmt.Printf("Ingredients: %d\n", len(result.Data.Ingredients))
    fmt.Printf("Confidence: %.2f\n", result.ConfidenceScore)
}
```

---

## 🏃 Running the API

### Local Development

```bash
# Activate virtual environment
source venv/bin/activate

# Start server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Access Swagger docs
open http://localhost:8000/docs
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# Or with Docker directly
docker build -t ekitchen-parser .
docker run -p 8000:8000 ekitchen-parser
```

---

## 📊 Supported Recipe Sites

The API supports **200+ recipe websites** including:

✅ AllRecipes
✅ Food Network
✅ Bon Appétit
✅ Serious Eats
✅ Simply Recipes
✅ Tasty
✅ BBC Good Food
✅ Jamie Oliver
✅ And 190+ more!

Full list: https://github.com/hhursev/recipe-scrapers#scrapers-available-for

---

## 🎯 Response Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Recipe title |
| `description` | string | Recipe description/summary |
| `ingredients` | string[] | Raw ingredient strings (e.g., "1 cup flour") |
| `steps` | string[] | Cooking instructions in order |
| `servings` | int | Number of servings (nullable) |
| `prep_time_minutes` | int | Preparation time in minutes (nullable) |
| `cook_time_minutes` | int | Cooking time in minutes (nullable) |
| `total_time_minutes` | int | Total time in minutes (nullable) |
| `image_url` | string | URL to recipe image (nullable) |
| `video_url` | string | URL to recipe video (nullable, usually null) |
| `source_metadata` | object | Author, site name, host, URL |
| `confidence_score` | float | Quality score 0.0-1.0 (1.0 = perfect) |
| `warnings` | string[] | Non-fatal issues (e.g., missing data) |

---

## ⚠️ Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_URL` | 400 | Malformed URL |
| `NOT_FOUND` | 404 | Recipe page not found |
| `UNSUPPORTED_SITE` | 404 | Website not supported by parser |
| `FORBIDDEN` | 403 | Access denied (paywall, auth required) |
| `TIMEOUT` | 504 | Request took too long |
| `NETWORK_ERROR` | 500 | Connection failure |
| `PARSING_FAILED` | 500 | Generic parsing error |
| `NOT_IMPLEMENTED` | 501 | Parser not yet implemented |

---

## 🔥 Next Steps

1. **Deploy to Railway** - Use the Dockerfile for production deployment
2. **Add Image Parser** - GPT-4 Vision for recipe screenshots
3. **Add Video Parser** - TikTok/YouTube recipe extraction
4. **Integrate with Go Backend** - Use the Go client example above

---

## 📚 Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

**Your API is ready to use! 🎉**
