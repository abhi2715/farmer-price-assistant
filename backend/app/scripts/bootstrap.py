"""One-shot init used by `docker compose up` (and `make dev`): seed -> train -> forecast -> match -> alerts.

Every step is idempotent and skipped when already done, so restarting the stack is cheap.
    python -m app.scripts.bootstrap [--force-train]
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.ingestion.pipeline import run_scheduled_ingestion
from app.models import Forecast, PriceHistory
from app.scripts import seed
from app.services import forecasting
from app.services.marketplace import run_matching
from app.services.notify import generate_price_alerts

log = logging.getLogger("bootstrap")


def main(force_train: bool = False) -> None:
    t0 = time.time()
    s = get_settings()
    log.info("seeding (live APIs: %s)", s.use_live_apis)
    log.info("seed: %s", seed.run(live=s.use_live_apis))
    db = SessionLocal()
    try:
        log.info("catch-up ingestion: %s", run_scheduled_ingestion(db))
        if force_train or forecasting.active_model() is None:
            log.info("training models (seasonal naive vs Prophet vs LightGBM) ...")
            res = forecasting.train(db)
            log.info("trained %s in %ss, best=%s mean MAPE=%s", res["version"], res["train_seconds"], res["best_model"],
                     {k: round(v, 2) for k, v in res["metrics"]["mape_overall"].items()})
        last = db.scalar(select(func.max(PriceHistory.date)))
        have = db.scalar(select(func.count()).select_from(Forecast).where(Forecast.origin_date >= last - timedelta(days=0)))
        if force_train or not have:
            log.info("forecasts written: %s", forecasting.generate_forecasts(db))
        log.info("matches proposed: %s", len(run_matching(db)))
        log.info("alerts created: %s", generate_price_alerts(db))
    finally:
        db.close()
    log.info("bootstrap complete in %.0fs", time.time() - t0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-train", action="store_true")
    main(ap.parse_args().force_train)
