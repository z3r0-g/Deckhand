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
COPY api ./api
COPY db ./db
COPY integrations ./integrations
COPY scheduler ./scheduler
COPY services ./services
COPY utils ./utils

COPY app.py .
COPY config.py .

# Copy UI (your actual structure)
COPY web /app/web

RUN mkdir -p /app/data && chmod 777 /app/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:5000/health || exit 1

#DEV Start
CMD ["python", "app.py"]

#PRD Start
#CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]