"""Crops, mandis, price history, forecasts and the sell recommendation."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cache
from app.db import get_db
from app.models import Crop, Mandi, ModelRun, PriceHistory
from app.schemas import Lang, RecommendIn
from app.security import current_user
from app.services import forecasting
from app.services import recommend as rec
from app.services.logistics import road_km

router = APIRouter(tags=["insights"])


def crop_out(c: Crop) -> dict:
    return {"id": c.id, "code": c.code, "name_en": c.name_en, "name_hi": c.name_hi, "name_kn": c.name_kn,
            "category": c.category, "emoji": c.emoji, "perishable": c.perishability_k >= 0.02}


@router.get("/crops")
def crops(db: Session = Depends(get_db)):
    return [crop_out(c) for c in db.scalars(select(Crop).order_by(Crop.id))]


@router.get("/mandis")
def mandis(lat: float | None = None, lon: float | None = None, crop_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Mandi)
    if crop_id:
        q = q.where(Mandi.id.in_(select(PriceHistory.mandi_id).where(PriceHistory.crop_id == crop_id).distinct()))
    out = []
    for m in db.scalars(q):
        d = {"id": m.id, "code": m.code, "name": m.name, "district": m.district, "lat": m.lat, "lon": m.lon,
             "market_fee_pct": m.market_fee_pct, "commission_pct": m.commission_pct, "hamali_per_qtl": m.hamali_per_qtl}
        if lat is not None and lon is not None:
            d["distance_km"] = road_km(lat, lon, m.lat, m.lon)
        out.append(d)
    return sorted(out, key=lambda d: d.get("distance_km", d["id"]))


@router.get("/prices")
def prices(crop_id: int, mandi_id: int, days: int = Query(90, ge=7, le=1500), db: Session = Depends(get_db)):
    last = db.scalar(select(func.max(PriceHistory.date)).where(PriceHistory.crop_id == crop_id, PriceHistory.mandi_id == mandi_id))
    if last is None:
        raise HTTPException(404, "no prices for this crop at this mandi")
    rows = db.execute(select(PriceHistory.date, PriceHistory.min_price, PriceHistory.modal_price, PriceHistory.max_price,
                             PriceHistory.arrivals_tonnes, PriceHistory.is_imputed)
                      .where(PriceHistory.crop_id == crop_id, PriceHistory.mandi_id == mandi_id,
                             PriceHistory.date > last - timedelta(days=days)).order_by(PriceHistory.date)).all()
    return [dict(date=r[0].isoformat(), min=r[1], modal=r[2], max=r[3], arrivals=r[4], imputed=r[5]) for r in rows]


@router.get("/forecasts")
def forecast(crop_id: int, mandi_id: int, horizon: int = Query(30, ge=1, le=30), history_days: int = Query(60, ge=0, le=365),
             lang: Lang = "en", explain: bool = True, db: Session = Depends(get_db)):
    key = f"fc:{crop_id}:{mandi_id}:{horizon}:{history_days}:{lang}:{explain}"
    if (hit := cache.get_json(key)) is not None:
        return hit
    fc = forecasting.latest_forecast(db, crop_id, mandi_id)
    if fc.empty:
        raise HTTPException(404, "no forecast available for this crop/mandi yet")
    fc = fc[fc["horizon"] <= horizon]
    hist = prices(crop_id, mandi_id, max(history_days, 7), db) if history_days else []
    run = db.scalar(select(ModelRun).where(ModelRun.is_active.is_(True)).order_by(ModelRun.id.desc()))
    mape = None
    if run:
        mape = run.metrics.get("mape_by_horizon", {}).get(run.best_model, {})
    last_price = hist[-1]["modal"] if hist else None
    pts = [dict(date=r.target_date.isoformat(), horizon=int(r.horizon), yhat=round(r.yhat), lo=round(r.yhat_lo), hi=round(r.yhat_hi))
           for r in fc.itertuples()]
    summary = {}
    for h in (7, 14, 30):
        p = next((x for x in pts if x["horizon"] == h), None)
        if p and last_price:
            summary[str(h)] = {**p, "change_pct": round((p["yhat"] / last_price - 1) * 100, 1),
                               "mape": round(mape.get(str(h), mape.get(h, 0)), 1) if mape else None}
    out = {"crop_id": crop_id, "mandi_id": mandi_id, "origin_date": fc["origin_date"].iloc[0].isoformat(),
           "model": fc["model_name"].iloc[0], "model_version": fc["model_version"].iloc[0], "interval": "80%",
           "last_price": last_price, "history": hist, "forecast": pts, "summary": summary,
           "why": forecasting.explain(db, crop_id, mandi_id, min(7, horizon), lang) if explain else None}
    cache.set_json(key, out, ttl=900)
    return out


@router.post("/recommend")
def recommend(body: RecommendIn, lang: Lang | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Crop, body.crop_id) is None:
        raise HTTPException(404, "unknown crop")
    prof = user.farmer or user.buyer
    lat = body.lat if body.lat is not None else (prof.lat if prof else 12.97)
    lon = body.lon if body.lon is not None else (prof.lon if prof else 77.59)
    res = rec.recommend(db, body.crop_id, body.quantity_qtl, lat, lon, lang or user.language, body.max_wait_days)
    if res["best"] is None:
        raise HTTPException(404, "no market data for this crop near you")
    return res
