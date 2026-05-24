FROM python:3.13-slim

WORKDIR /app

# Install system dependencies if needed (e.g., for SQLite or potential future tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Force cache invalidation for every build
ARG BUILD_ID=0
RUN echo "Build ID: $BUILD_ID"

# Copy the rest of the application
COPY . .

# Create data directory for SQLite persistence
RUN mkdir -p /app/data && chmod 777 /app/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5000/health || exit 1

CMD ["python", "app.py"]