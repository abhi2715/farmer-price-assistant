"""DB <-> ML bridge: load training frames, train, store forecasts, serve them, explain them."""
from __future__ import annotations

import logging
import threading
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from agriroute_ml.features import BASE_FEATURES, FEATURES, H_FEATURES, build_panel, horizon_frame
from agriroute_ml.forecast import ActiveModel, forecast_latest, load_active
from agriroute_ml.train import run_training
from app.config import get_settings
from app.db import upsert
from app.i18n import t
from app.models import CalendarEvent, Crop, Forecast, Mandi, ModelRun, Msp, PriceHistory, Weather

log = logging.getLogger(__name__)
_lock = threading.Lock()
_active: ActiveModel | None = None


def active_model(reload: bool = False) -> ActiveModel | None:
    """Process-wide cached model; reloads when the registry points to a new version."""
    global _active
    s = get_settings()
    with _lock:
        if reload or _active is None:
            _active = load_active(s.model_dir)
        else:
            import json
            from pathlib import Path

            reg = Path(s.model_dir) / "registry.json"
            if reg.exists() and json.loads(reg.read_text())["active"] != _active.version:
                _active = load_active(s.model_dir)
    return _active


# ----- frames ---------------------------------------------------------------------------------
def load_frames(db: Session, crop_id: int | None = None, mandi_id: int | None = None, since: date | None = None):
    bind = db.connection()
    q = (select(Crop.code.label("crop"), Mandi.code.label("mandi"), PriceHistory.date, PriceHistory.modal_price,
                PriceHistory.arrivals_tonnes, PriceHistory.is_imputed)
         .join(Crop, Crop.id == PriceHistory.crop_id).join(Mandi, Mandi.id == PriceHistory.mandi_id))
    wq = select(Mandi.code.label("mandi"), Weather.date, Weather.temp_max, Weather.rain_mm).join(Mandi, Mandi.id == Weather.mandi_id)
    if crop_id:
        q = q.where(PriceHistory.crop_id == crop_id)
    if mandi_id:
        q = q.where(PriceHistory.mandi_id == mandi_id)
        wq = wq.where(Weather.mandi_id == mandi_id)
    if since:
        q = q.where(PriceHistory.date >= since)
        wq = wq.where(Weather.date >= since)
    prices = pd.read_sql(q, bind)
    weather = pd.read_sql(wq.where(Weather.is_forecast.is_(False)), bind)
    events = pd.read_sql(select(CalendarEvent.date, CalendarEvent.name, CalendarEvent.demand_impact), bind)
    msp = pd.read_sql(select(Crop.code.label("crop"), Msp.season_year, Msp.price).join(Crop, Crop.id == Msp.crop_id), bind)
    for df in (prices, weather, events):
        df["date"] = pd.to_datetime(df["date"])
    prices["is_imputed"] = prices["is_imputed"].astype(bool)
    return prices, weather, events, msp


# ----- training & batch forecasts ---------------------------------------------------------------
def train(db: Session, enable_prophet: bool | None = None) -> dict:
    s = get_settings()
    prices, weather, events, msp = load_frames(db)
    if prices.empty:
        raise RuntimeError("no price data - run the seed first")
    res = run_training(prices, weather, events, msp, s.model_dir, s.report_dir,
                       enable_prophet=s.enable_prophet if enable_prophet is None else enable_prophet,
                       n_series=s.backtest_series, n_origins=s.backtest_origins, num_boost_round=s.lgbm_rounds, mlflow_uri=s.mlflow_tracking_uri)
    db.execute(ModelRun.__table__.update().values(is_active=False))
    db.add(ModelRun(version=res["version"], best_model=res["best_model"], metrics=res["metrics"],
                    report_path=res["report_path"], is_active=True))
    db.commit()
    active_model(reload=True)
    return res


def generate_forecasts(db: Session, max_h: int = 30) -> int:
    model = active_model()
    if model is None:
        raise RuntimeError("no trained model")
    last = db.scalar(select(func.max(PriceHistory.date)))
    prices, weather, events, msp = load_frames(db, since=last - timedelta(days=800))
    panel = build_panel(prices, weather, events, msp, end=pd.Timestamp(last))
    fc = forecast_latest(panel, events, model, max_h=max_h)
    crops = dict(db.execute(select(Crop.code, Crop.id)).all())
    mandis = dict(db.execute(select(Mandi.code, Mandi.id)).all())
    rows = [dict(crop_id=crops[r.crop], mandi_id=mandis[r.mandi], origin_date=r.origin_date, target_date=r.target_date,
                 horizon=int(r.horizon), yhat=round(float(r.yhat), 1), yhat_lo=round(float(r.yhat_lo), 1),
                 yhat_hi=round(float(r.yhat_hi), 1), model_name=r.model_name, model_version=r.model_version)
            for r in fc.itertuples()]
    n = upsert(db, Forecast, rows, ["crop_id", "mandi_id", "origin_date", "target_date"])
    db.execute(delete(Forecast).where(Forecast.origin_date < last - timedelta(days=60)))
    db.commit()
    return n


# ----- serving --------------------------------------------------------------------------------
def latest_forecast(db: Session, crop_id: int, mandi_id: int | None = None) -> pd.DataFrame:
    """Most recent forecast run for a crop (optionally one mandi)."""
    q = select(Forecast).where(Forecast.crop_id == crop_id)
    if mandi_id:
        q = q.where(Forecast.mandi_id == mandi_id)
    sub = select(Forecast.mandi_id, func.max(Forecast.origin_date).label("o")).where(Forecast.crop_id == crop_id)
    sub = sub.group_by(Forecast.mandi_id).subquery()
    q = q.join(sub, (sub.c.mandi_id == Forecast.mandi_id) & (sub.c.o == Forecast.origin_date)).order_by(Forecast.mandi_id, Forecast.horizon)
    rows = db.scalars(q).all()
    return pd.DataFrame([dict(mandi_id=r.mandi_id, origin_date=r.origin_date, target_date=r.target_date, horizon=r.horizon,
                              yhat=r.yhat, yhat_lo=r.yhat_lo, yhat_hi=r.yhat_hi, model_name=r.model_name,
                              model_version=r.model_version) for r in rows])


def last_prices(db: Session, crop_id: int) -> dict[int, tuple[date, float]]:
    sub = (select(PriceHistory.mandi_id, func.max(PriceHistory.date).label("d"))
           .where(PriceHistory.crop_id == crop_id).group_by(PriceHistory.mandi_id).subquery())
    q = select(PriceHistory.mandi_id, PriceHistory.date, PriceHistory.modal_price).join(
        sub, (sub.c.mandi_id == PriceHistory.mandi_id) & (sub.c.d == PriceHistory.date)).where(PriceHistory.crop_id == crop_id)
    return {m: (d, p) for m, d, p in db.execute(q).all()}


# ----- explainability ---------------------------------------------------------------------------
FEATURE_GROUP = {
    "seas_prior": "seasonal", "target_doy_sin": "seasonal", "target_doy_cos": "seasonal",
    "fest_now": "festival", "days_to_fest": "festival", "fest_target": "festival", "fest_peak_in_window": "festival",
    "r1": "trend", "r7": "trend", "r14": "trend", "r30": "trend", "vol14": "trend",
    "dev_ma7": "level", "dev_ma30": "level", "dev_ma90": "level", "dev_ma365": "level", "yoy": "level",
    "arr_ratio": "arrivals", "arr_yoy": "arrivals",
    "rain7": "rain", "rain30": "rain", "tmax7": "rain",
    "msp_ratio": "msp", "crop": "market", "mandi": "market", "h": "market",
}
assert set(FEATURE_GROUP) == set(FEATURES) == set(BASE_FEATURES + H_FEATURES + ["crop", "mandi"])


def explain(db: Session, crop_id: int, mandi_id: int, horizon: int, lang: str = "en", top: int = 3) -> dict:
    """SHAP contributions for one forecast, grouped into plain-language reasons."""
    model = active_model()
    if model is None or horizon < 1:
        return {"reasons": [], "method": None}
    last = db.scalar(select(func.max(PriceHistory.date)).where(PriceHistory.crop_id == crop_id, PriceHistory.mandi_id == mandi_id))
    prices, weather, events, msp = load_frames(db, crop_id, mandi_id, since=last - timedelta(days=420))
    if prices.empty:
        return {"reasons": [], "method": None}
    panel = build_panel(prices, weather, events, msp)
    hf = horizon_frame(panel, min(horizon, 30), events, with_target=False)
    row = hf[hf["date"] == hf["date"].max()]
    if row["crop"].iloc[0] not in model.lgbm.categories["crop"] or row["mandi"].iloc[0] not in model.lgbm.categories["mandi"]:
        return {"reasons": [], "method": None}
    sv = model.shap_values(row)[0]
    groups: dict[str, float] = {}
    for f, v in zip(FEATURES, sv):
        groups[FEATURE_GROUP[f]] = groups.get(FEATURE_GROUP[f], 0.0) + float(v)
    groups.pop("market", None)
    ordered = sorted(groups.items(), key=lambda kv: -abs(kv[1]))
    total = sum(abs(v) for _, v in ordered) or 1.0
    ev = events.sort_values("date")
    target = row["date"].iloc[0] + pd.Timedelta(days=horizon)
    nxt = ev[ev["date"] >= row["date"].iloc[0]]
    prev = ev[ev["date"] <= target]
    reasons = []
    for g, v in ordered[:top]:
        if abs(v) < 0.002:  # < 0.2% effect - not worth saying
            continue
        direction = "up" if v > 0 else "down"
        festival = (nxt["name"].iloc[0] if direction == "up" and len(nxt) else prev["name"].iloc[-1] if len(prev) else "")
        reasons.append(dict(group=g, direction=direction, impact_pct=round((np.exp(v) - 1) * 100, 1),
                            weight=round(abs(v) / total, 2), text=t(f"{g}.{direction}", lang, festival=festival)))
    return {"reasons": reasons, "method": "TreeSHAP (LightGBM)", "model_version": model.version,
            "base_change_pct": round(float(np.exp(sv.sum()) - 1) * 100, 1)}
