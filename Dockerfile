FROM python:3.14-rc-slim

WORKDIR /app

# Install system dependencies if needed (e.g., for SQLite or potential future tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

EXPOSE 5000
CMD ["python", "app.py"]