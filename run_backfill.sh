#!/bin/bash
cd /Users/ramiz/ekitchen/ekitchen-ingestion
source local.env
source venv/bin/activate

# Export the env vars explicitly
export EKITCHEN_BASE_URL
export EKITCHEN_ADMIN_EMAIL
export EKITCHEN_ADMIN_PASSWORD
export OPENAI_API_KEY

python3 scripts/backfill_dietary_classification.py "$@"
