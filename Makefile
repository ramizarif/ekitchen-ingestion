SHELL := /bin/bash

VENV_PYTHON := venv/bin/python3
INGEST_SCRIPT := tools/recipe-ingestion/interactive_recipe_ingestion.py
BACKFILL_IMAGES_SCRIPT := scripts/backfill_recipe_images.py
BACKFILL_NAMES_SCRIPT := scripts/backfill_recipe_names.py

# Override flags for backfill targets, e.g. `make backfill-images ARGS="--dry-run --limit 10"`
ARGS ?=

.PHONY: ingest backfill-images backfill-names

ingest:
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		echo "❌ venv not found at $(VENV_PYTHON) — run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"; \
		exit 1; \
	fi
	@if [ ! -f local.env ]; then \
		echo "❌ local.env missing — copy local.env.development.example to local.env and fill in your keys"; \
		exit 1; \
	fi
	@echo "🍽️  Launching interactive recipe ingestion..."
	@echo "📡 Target: $$(grep '^EKITCHEN_BASE_URL=' local.env | cut -d'=' -f2-)"
	@cd tools/recipe-ingestion && set -a && source ../../local.env && set +a && PYTHONPATH=../../legacy/src/processing:../../legacy/src/discovery:$$PYTHONPATH ../../$(VENV_PYTHON) interactive_recipe_ingestion.py

backfill-images:
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		echo "❌ venv not found at $(VENV_PYTHON) — run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"; \
		exit 1; \
	fi
	@if [ ! -f local.env ]; then \
		echo "❌ local.env missing — copy local.env.development.example to local.env and fill in your keys"; \
		exit 1; \
	fi
	@echo "🖼️  Backfilling DALL-E hero images for recipes missing one..."
	@echo "📡 Target: $$(grep '^EKITCHEN_BASE_URL=' local.env | cut -d'=' -f2-)"
	@echo "💡 Tip: pass flags via ARGS, e.g. \`make backfill-images ARGS=\"--dry-run\"\`"
	@set -a && source local.env && set +a && $(VENV_PYTHON) $(BACKFILL_IMAGES_SCRIPT) $(ARGS)

backfill-names:
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		echo "❌ venv not found at $(VENV_PYTHON) — run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"; \
		exit 1; \
	fi
	@if [ ! -f local.env ]; then \
		echo "❌ local.env missing — copy local.env.development.example to local.env and fill in your keys"; \
		exit 1; \
	fi
	@echo "🧹 Stripping publisher attribution from recipe names..."
	@echo "📡 Target: $$(grep '^EKITCHEN_BASE_URL=' local.env | cut -d'=' -f2-)"
	@echo "💡 Tip: pass flags via ARGS, e.g. \`make backfill-names ARGS=\"--dry-run\"\`"
	@set -a && source local.env && set +a && $(VENV_PYTHON) $(BACKFILL_NAMES_SCRIPT) $(ARGS)
