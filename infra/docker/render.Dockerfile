# Single-container API for Render's free tier (512 MB RAM, no persistent disk, sleeps when idle).
# - The forecasting model is trained at BUILD time on the deterministic synthetic dataset (same data the
#   app seeds into Postgres), so a cold start only loads it instead of retraining.
# - Prophet is left out (big, and it only competes in the backtest); LightGBM serves.
# - No Redis/Celery: cache, OTP and rate limits run in memory and a background thread replaces beat.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MODEL_DIR=/data/models REPORT_DIR=/data/reports ENABLE_PROPHET=false
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/
COPY ml/requirements.txt ml/pyproject.toml /app/ml/
RUN grep -v -i '^prophet' ml/requirements.txt > /tmp/ml-req.txt \
    && pip install -r backend/requirements.txt -r /tmp/ml-req.txt
COPY ml /app/ml
RUN pip install --no-deps -e /app/ml
COPY backend /app/backend
WORKDIR /app/backend
RUN DATABASE_URL=sqlite:////tmp/build.db sh -c "alembic upgrade head && python -m app.scripts.bootstrap" \
    && rm -rf /tmp/build.db* mlruns notifications_outbox.jsonl \
    && useradd -m -u 1000 agri && chown -R agri /data /app
USER agri
# Render injects $PORT. Migrations are quick; seeding/forecasting runs in a background thread (BOOTSTRAP_ON_STARTUP).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips '*'"]
