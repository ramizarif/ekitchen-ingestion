# eKitchen Recipe Parser API

Python parsing service for extracting structured recipe data from various sources for the eKitchen application.

## 🎯 What This Does

REST API that accepts URLs (websites, videos, images) and returns structured recipe JSON data that eKitchen's Go backend can ingest.

### Supported Sources

- 🌐 **Websites**: 200+ recipe sites via [recipe-scrapers](https://github.com/hhursev/recipe-scrapers)
- 📹 **Videos**: TikTok, YouTube, Instagram (GPT-4 Vision) - *Coming Soon*
- 📸 **Images**: Recipe screenshots (GPT-4 Vision) - *Coming Soon*
- 📄 **PDFs**: Recipe documents - *Future*

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- OpenAI API key (for video/image parsing)
- Spoonacular API key (optional, for enrichment)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env and add your API keys
```

### Running Locally

```bash
# Development server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using the API

```bash
# Parse a recipe from a website
curl -X POST http://localhost:8000/api/v1/parse \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.allrecipes.com/recipe/12345/chocolate-cake/",
    "source_type": "website"
  }'

# Check health
curl http://localhost:8000/health

# API documentation (Swagger UI)
open http://localhost:8000/docs
```

## 📁 Project Structure

```
ekitchen-ingestion/
├── app/                    # FastAPI application (PRIMARY)
│   ├── main.py            # FastAPI app entry point
│   ├── models.py          # Request/response models
│   ├── config.py          # Configuration
│   └── routers/           # API endpoints
│       ├── parse.py       # /parse endpoint
│       └── health.py      # Health checks
│
├── parsers/               # Parser implementations
│   ├── base.py           # Abstract base parser
│   ├── website.py        # Website parser (recipe-scrapers)
│   ├── image.py          # Image parser (GPT-4 Vision)
│   ├── video.py          # Video parser (GPT-4 Vision)
│   └── utils/            # Parser utilities
│
├── services/             # External service clients
│   ├── openai_client.py  # OpenAI wrapper
│   └── spoonacular_client.py
│
├── tools/                # Operational scripts (SECONDARY)
│   ├── data-maintenance/ # Database maintenance scripts
│   └── recipe-ingestion/ # Manual recipe ingestion workflows
│
├── tests/                # Test suite
├── config/               # Configuration files
├── data/                 # Recipe data (gitignored)
├── docs/                 # Documentation
└── legacy/               # Historical code (archived)
```

## 🛠 Development

### API Development

Primary focus of this repository. See [docs/api/](docs/api/) for detailed API documentation.

### Tools (Secondary)

Operational scripts for database maintenance and manual recipe ingestion:

- **Data Maintenance** (`tools/data-maintenance/`): Scripts to fix/enrich existing eKitchen database data
- **Recipe Ingestion** (`tools/recipe-ingestion/`): Manual bulk recipe ingestion workflows

These are kept for operational use but are not the primary focus of this repository.

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=parsers

# Run specific test file
pytest tests/test_website_parser.py
```

## 📚 Documentation

- [API Documentation](docs/api/API.md) - Complete API reference
- [Parser Guide](docs/api/PARSERS.md) - How to implement new parsers
- [Deployment Guide](docs/api/DEPLOYMENT.md) - Railway deployment
- [Tools Documentation](docs/tools/) - Data maintenance and ingestion tools

## 🚢 Deployment

See [docs/api/DEPLOYMENT.md](docs/api/DEPLOYMENT.md) for Railway deployment instructions.

## 🤝 Integration with eKitchen

This service integrates with the eKitchen Go backend:

1. **User submits URL** → eKitchen mobile app
2. **eKitchen Go API** → Creates `recipe_imports` record, calls this Python API
3. **Python API** → Parses recipe, returns structured JSON
4. **eKitchen Go API** → Handles ingredient matching, duplicate detection, database creation

The Python API is **stateless** and **focused on parsing only**. All business logic (auth, database, duplicates) lives in the Go backend.

## 📝 License

MIT

## 🔗 Related Repositories

- [eKitchen Backend](https://github.com/yourorg/ekitchen-backend) - Go modular monolith
- [eKitchen Mobile](https://github.com/yourorg/ekitchen-mobile) - Flutter app
