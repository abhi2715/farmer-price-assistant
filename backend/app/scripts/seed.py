"""Seed script: reference data, prices/weather (live APIs or synthetic), demo users, demands and lots.

    python -m app.scripts.seed            # idempotent; safe to re-run
    python -m app.scripts.seed --live     # try Agmarknet/Open-Meteo first, synthetic fallback
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingestion import pipeline
from app.models import Buyer, Crop, Demand, Farmer, FarmerCrop, Lot, PriceHistory, User
from app.seed.synthetic import ADMIN_PHONE, DEMO_BUYERS, DEMO_DEMANDS, DEMO_FARMERS

log = logging.getLogger("seed")

# Lots posted by the other demo farmers so buyers see activity. Farmer #1 (demo login) starts empty.
DEMO_LOTS = [
    # farmer phone, crop, grade, qty, ask markup vs state price
    ("9000000002", "potato", "A", 25, 0.98),
    ("9000000003", "onion", "B", 60, 0.97),
    ("9000000004", "banana", "A", 15, 0.98),
    ("9000000005", "tur", "B", 30, 0.99),
]


def state_price(db: Session, crop_id: int) -> float:
    last = db.scalar(select(func.max(PriceHistory.date)).where(PriceHistory.crop_id == crop_id))
    return float(db.scalar(select(func.avg(PriceHistory.modal_price)).where(
        PriceHistory.crop_id == crop_id, PriceHistory.date > last - timedelta(days=7))))


def seed_users(db: Session) -> None:
    crops = dict(db.execute(select(Crop.code, Crop.id)).all())
    if not db.scalar(select(User.id).where(User.phone == ADMIN_PHONE)):
        db.add(User(phone=ADMIN_PHONE, name="AgriRoute Admin", role="admin"))
    for phone, name, village, district, lat, lon, lang, cs in DEMO_FARMERS:
        if db.scalar(select(User.id).where(User.phone == phone)):
            continue
        u = User(phone=phone, name=name, role="farmer", language=lang)
        db.add(u)
        db.flush()
        f = Farmer(user_id=u.id, village=village, district=district, lat=lat, lon=lon, land_acres=4,
                   whatsapp_opt_in=phone.endswith("1"))
        db.add(f)
        db.flush()
        db.add_all([FarmerCrop(farmer_id=f.id, crop_id=crops[c]) for c in cs])
    for phone, name, biz, kind, district, lat, lon in DEMO_BUYERS:
        if db.scalar(select(User.id).where(User.phone == phone)):
            continue
        u = User(phone=phone, name=name, role="buyer")
        db.add(u)
        db.flush()
        db.add(Buyer(user_id=u.id, business_name=biz, buyer_type=kind, district=district, lat=lat, lon=lon))
    db.commit()


def seed_market(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Demand)):
        return
    crops = dict(db.execute(select(Crop.code, Crop.id)).all())
    today = date.today()
    for phone, crop, grade, qty, markup, km in DEMO_DEMANDS:
        b = db.scalar(select(Buyer).join(User).where(User.phone == phone))
        cid = crops[crop]
        db.add(Demand(buyer_id=b.id, crop_id=cid, min_grade=grade, quantity_qtl=qty, remaining_qtl=qty,
                      max_price=round(state_price(db, cid) * markup), lat=b.lat, lon=b.lon, max_distance_km=km,
                      needed_by=today + timedelta(days=21)))
    for phone, crop, grade, qty, markup in DEMO_LOTS:
        f = db.scalar(select(Farmer).join(User).where(User.phone == phone))
        cid = crops[crop]
        db.add(Lot(farmer_id=f.id, crop_id=cid, grade=grade, quantity_qtl=qty, remaining_qtl=qty,
                   ask_price=round(state_price(db, cid) * markup), lat=f.lat, lon=f.lon, available_from=today))
    db.commit()


def run(live: bool = False) -> dict:
    db = SessionLocal()
    try:
        pipeline.load_reference(db)
        out = {}
        if live:
            try:
                out["live"] = pipeline.ingest_live(db)
            except Exception as e:
                db.rollback()
                log.warning("live APIs unavailable (%s) - using synthetic data", e)
        have = db.scalar(select(func.count()).select_from(PriceHistory))
        if have < 1000:  # live feed only gives today's snapshot; history comes from the synthetic backfill
            out["synthetic"] = pipeline.ingest_synthetic(db)
        seed_users(db)
        seed_market(db)
        out["price_rows"] = db.scalar(select(func.count()).select_from(PriceHistory))
        return out
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    print(run(ap.parse_args().live))
