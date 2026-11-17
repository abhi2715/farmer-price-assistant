"""DB wrapper around the optimizer: assemble forecasts, weather and costs, then rank and explain."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.i18n import t
from app.models import Crop, Mandi, PriceHistory, Weather
from app.services import forecasting
from app.services.logistics import road_km
from app.services.optimizer import CropInfo, MandiInfo, rank_options, split_plan


def _mandi_infos(db: Session, crop_id: int) -> list[MandiInfo]:
    since = db.scalar(select(func.max(PriceHistory.date))) or date.today()
    arr = dict(db.execute(
        select(PriceHistory.mandi_id, func.avg(PriceHistory.arrivals_tonnes))
        .where(PriceHistory.crop_id == crop_id, PriceHistory.date >= since - timedelta(days=60))
        .group_by(PriceHistory.mandi_id)).all())
    out = []
    for m in db.scalars(select(Mandi).where(Mandi.id.in_(arr.keys()))):
        out.append(MandiInfo(m.id, m.name, m.lat, m.lon, m.market_fee_pct, m.commission_pct, m.hamali_per_qtl,
                             daily_arrivals_qtl=float(arr.get(m.id) or 100) * 10))
    return out


def recommend(db: Session, crop_id: int, qty: float, lat: float, lon: float, lang: str = "en",
              max_wait_days: int = 14, today: date | None = None) -> dict:
    crop = db.get(Crop, crop_id)
    cinfo = CropInfo(crop.id, crop.code, crop.perishability_k, crop.storage_cost_per_qtl_day)
    mandis = _mandi_infos(db, crop_id)
    fc = forecasting.latest_forecast(db, crop_id)
    last = forecasting.last_prices(db, crop_id)
    today = today or date.today()
    # price lookup: observed price for the data's "today", forecast for future dates
    by = {}
    for r in fc.itertuples():
        by[(r.mandi_id, r.target_date)] = (r.yhat, r.yhat_lo, r.yhat_hi, r.horizon)
    model_name = fc["model_name"].iloc[0] if len(fc) else "last_price"

    def price_fn(mid: int, d: date):
        if (mid, d) in by:
            return by[(mid, d)]
        if mid in last and d <= last[mid][0] + timedelta(days=1):
            p = last[mid][1]
            return (p, p * 0.97, p * 1.03, 0)
        return None

    # Weather: forecast temps when stored, otherwise last 7-day mean
    w = dict(((m, d), (tmax, tmin)) for m, d, tmax, tmin in db.execute(
        select(Weather.mandi_id, Weather.date, Weather.temp_max, Weather.temp_min)
        .where(Weather.date >= today - timedelta(days=7), Weather.date <= today + timedelta(days=max_wait_days))).all())

    def temp_fn(mid: int, d0: date, d1: date) -> float:
        vals = [(a + b) / 2 for (m, d), (a, b) in w.items() if m == mid and d0 - timedelta(days=7) <= d <= d1 and a is not None and b is not None]
        return sum(vals) / len(vals) if vals else 25.0

    # Data may lag the wall clock (e.g. Agmarknet publishes late): anchor "today" to the data
    data_today = max((v[0] for v in last.values()), default=today)
    if data_today < today - timedelta(days=1):
        today = data_today + timedelta(days=1)
    opts = rank_options(cinfo, qty, (lat, lon), mandis, price_fn, temp_fn, today, max_wait_days)
    if not opts:
        return {"options": [], "best": None, "explanation": [], "split_plan": None}

    best = opts[0]
    nearest = min(mandis, key=lambda m: road_km(lat, lon, m.lat, m.lon))
    base = next((o for o in opts if o.mandi_id == nearest.id and o.days_wait == 0), None) or \
        next((o for o in sorted(opts, key=lambda o: o.days_wait) if o.mandi_id == nearest.id), None)
    best_per_mandi = {}
    for o in opts:
        best_per_mandi.setdefault(o.mandi_id, o)

    # ---- plain-language explanation ----
    lines = []
    if base and (base.mandi_id, base.sell_date) != (best.mandi_id, best.sell_date):
        lines.append(t("decision.best_vs_nearest", lang, best=best.mandi_name, nearest=nearest.name, gain=best.net - base.net))
    else:
        lines.append(t("decision.best_is_nearest", lang, best=best.mandi_name))
    sell_now_here = next((o for o in opts if o.mandi_id == best.mandi_id and o.days_wait == 0), None)
    if best.days_wait > 0 and sell_now_here:
        lines.append(t("decision.wait", lang, days=best.days_wait, p0=sell_now_here.price, p1=best.price))
    elif best.days_wait == 0:
        lines.append(t("decision.sell_now", lang))
    lines.append(t("decision.costs", lang, transport=best.transport, vehicle=t(f"vehicle.{best.vehicle}", lang),
                   km=round(best.distance_km), fees=best.fees, spoil=round(best.spoilage_pct, 1)))
    lines.append(t("decision.risk", lang, net_lo=best.net_lo))
    why = forecasting.explain(db, crop_id, best.mandi_id, best.horizon, lang) if best.horizon > 0 else {"reasons": []}

    plan = split_plan(cinfo, qty, (lat, lon), opts, {m.id: m for m in mandis}, today)
    if plan and len([a for a in plan.allocations if a["mandi_id"]]) > 1 and plan.total_net > best.net:
        lines.append(t("decision.split", lang, n=len(plan.allocations), gain=plan.total_net - best.net))
    else:
        plan = None

    return {
        "crop": {"id": crop.id, "code": crop.code, "name": getattr(crop, f"name_{lang}", crop.name_en)},
        "quantity_qtl": qty,
        "as_of": today.isoformat(),
        "model": model_name,
        "best": best.to_dict(),
        "baseline": base.to_dict() if base else None,
        "gain_vs_baseline": round(best.net - base.net, 0) if base else None,
        "options": [o.to_dict() for o in opts[:10]],
        "best_per_mandi": [o.to_dict() for o in sorted(best_per_mandi.values(), key=lambda o: -o.net)],
        "explanation": lines,
        "why_price": why,
        "split_plan": plan.to_dict() if plan else None,
    }
