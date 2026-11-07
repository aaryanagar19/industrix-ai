FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TF_CPP_MIN_LOG_LEVEL=3
WORKDIR /app/backend
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY models /app/models
ENV MODELS_DIR=/app/models DATA_DIR=/app/data STORAGE_DIR=/app/storage
RUN mkdir -p /app/storage /app/data && useradd -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]
