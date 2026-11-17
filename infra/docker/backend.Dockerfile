# API, Celery worker/beat and the one-shot init job share this image.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements-dev.txt /app/backend/
COPY ml/requirements.txt ml/pyproject.toml /app/ml/
RUN pip install -r backend/requirements.txt -r ml/requirements.txt -r backend/requirements-dev.txt
COPY ml /app/ml
RUN pip install -e /app/ml
COPY backend /app/backend
WORKDIR /app/backend
RUN useradd -m -u 1000 agri && mkdir -p /data/models /data/reports && chown -R agri /data /app \
    && python -c "from agriroute_ml.models import prophet_available; print('prophet', prophet_available())"
USER agri
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD curl -fsS localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
