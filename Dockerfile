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

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5.0)" || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
