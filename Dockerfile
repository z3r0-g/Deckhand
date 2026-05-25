FROM python:3.13-slim
WORKDIR /deckhand

#Set Environment Variables
ARG BUILD_ID=0
ARG PORT=5000
ENV NODE_ENV production
ENV PORT=${PORT}

#Install App Depedencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

#Install System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    && rm -rf /var/lib/apt/lists/*

#Invalidate Cache and Copy Source
RUN echo "Cache buster: $BUILD_ID"
COPY api ./api
COPY db ./db
COPY integrations ./integrations
COPY scheduler ./scheduler
COPY services ./services
COPY static ./static
COPY templates ./templates
COPY utils ./utils
COPY app.py ./
COPY cache.py ./
COPY config.py ./

#Create Data Directory
RUN mkdir -p /deckhand/data && chmod 777 /deckhand/data

#Expose Application Port
EXPOSE $PORT

#Health Check Configuration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT}/health || exit 1

#Application Startup [DEV]
CMD ["python", "app.py"]

#TODO: Install Gunicorn and switch to this command for final production deployment
#Application Startup [PROD]
#CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]