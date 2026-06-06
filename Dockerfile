# eKitchen Recipe Ingestion API
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including ffmpeg for video processing
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp for video downloading
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY parsers/ ./parsers/
COPY services/ ./services/
COPY config/ ./config/

# Create directories for generated images and temp files
RUN mkdir -p /app/data/generated-recipe-images/single-recipes \
    && mkdir -p /tmp/video_downloads

# Default port (Railway overrides via PORT or API_PORT env var)
ENV PORT=8000

# Expose port
EXPOSE ${PORT}

# Health check (uses localhost since this runs inside the container)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; import os; httpx.get(f'http://localhost:{os.environ.get(\"PORT\", os.environ.get(\"API_PORT\", 8000))}/health', timeout=5.0)" || exit 1

# Run the application. Bind to IPv6 wildcard '::' — Railway's private network
# (*.railway.internal) is IPv6-only, so the backend's dial to this service fails
# with "connection refused" if uvicorn binds IPv4-only (0.0.0.0). On Linux's
# dual-stack default (bindv6only=0) '::' also accepts IPv4, so this covers both.
# (Restores fix 77a62d0, silently reverted by a9a530e.)
# Multiple workers so a single in-flight request (recipe import OR receipt scan)
# can't head-of-line block the whole container. UVICORN_WORKERS overrides; default 4.
CMD sh -c "uvicorn app.main:app --host '::' --port ${PORT:-${API_PORT:-8000}} --workers ${UVICORN_WORKERS:-4}"
