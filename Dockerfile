FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build cache invalidation
ARG BUILD_ID=0
RUN echo "Build ID: $BUILD_ID"

# Copy backend code explicitly
COPY app ./app
COPY app.py .
COPY config.yaml .

# Copy UI templates and static assets explicitly
# This is the critical fix — ensures your updated UI is always included
COPY web/templates /app/web/templates
COPY web/static /app/web/static

# Create data directory for SQLite persistence
RUN mkdir -p /app/data && chmod 777 /app/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5000/health || exit 1

# Development command (uncomment for development use)
CMD ["python", "app.py"]

#Production command using Gunicorn (uncomment for production use)
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]