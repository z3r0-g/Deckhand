FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG BUILD_ID=0
RUN echo "Build ID: $BUILD_ID"

# Copy backend
COPY app ./app
COPY app.py .
COPY config.yaml .

# Copy UI (correct paths for your repo)
COPY web/deckhand.html /app/web/deckhand.html
COPY web/static /app/web/static

RUN mkdir -p /app/data && chmod 777 /app/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5000/health || exit 1

#DEV Start
CMD ["python", "app.py"]

#PRD Start
#CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]