"""Celery app, tasks and beat schedule. Without REDIS_URL tasks run eagerly in-process."""
import logging

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings
from app.db import SessionLocal

log = logging.getLogger(__name__)
_s = get_settings()
celery = Celery("agriroute", broker=_s.redis_url or "memory://", backend=_s.redis_url or "cache+memory://")
celery.conf.update(
    task_always_eager=not _s.redis_url,
    timezone="Asia/Kolkata",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Agmarknet publishes through the evening; pull at 21:30 and again early morning.
        "ingest-evening": {"task": "agriroute.ingest", "schedule": crontab(hour=21, minute=30)},
        "ingest-morning": {"task": "agriroute.ingest", "schedule": crontab(hour=6, minute=0)},
        "forecast-daily": {"task": "agriroute.forecast", "schedule": crontab(hour=6, minute=30)},
        "alerts-daily": {"task": "agriroute.alerts", "schedule": crontab(hour=7, minute=0)},
        "match-every-10m": {"task": "agriroute.match", "schedule": 600.0},
        "retrain-weekly": {"task": "agriroute.train", "schedule": crontab(hour=2, minute=0, day_of_week="sun")},
    },
)


def _with_db(fn):
    db = SessionLocal()
    try:
        return fn(db)
    finally:
        db.close()


@celery.task(name="agriroute.ingest", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def ingest_task():
    from app.ingestion.pipeline import run_scheduled_ingestion

    return _with_db(run_scheduled_ingestion)


@celery.task(name="agriroute.train")
def train_task():
    from app.services import forecasting

    def go(db):
        res = forecasting.train(db)
        forecasting.generate_forecasts(db)
        return {"version": res["version"], "best_model": res["best_model"]}

    return _with_db(go)


@celery.task(name="agriroute.forecast")
def forecast_task():
    from app.services import forecasting

    return _with_db(lambda db: {"rows": forecasting.generate_forecasts(db)})


@celery.task(name="agriroute.match")
def match_task():
    from app.services.marketplace import run_matching

    return _with_db(lambda db: {"matches": len(run_matching(db))})


@celery.task(name="agriroute.alerts")
def alerts_task():
    from app.services.notify import generate_price_alerts

    return _with_db(lambda db: {"alerts": generate_price_alerts(db)})
