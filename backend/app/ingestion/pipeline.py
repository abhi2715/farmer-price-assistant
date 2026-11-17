"""Idempotent ingestion: reference data, prices, weather, gap imputation.

Every write is an upsert on the natural key, so re-running any job (or the whole seed) is safe.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import upsert
from app.ingestion import sources
from app.ingestion.quality import check_prices, check_weather
from app.models import CalendarEvent, Crop, IngestionRun, Mandi, Msp, PriceHistory, Weather
from app.seed import synthetic
from app.seed.reference_data import CROPS, MANDIS, MSP, MSP_ESTIMATE_GROWTH

log = logging.getLogger(__name__)
IMPUTE_MAX_GAP_DAYS = 3


def load_reference(db: Session) -> None:
    upsert(db, Crop, [
        dict(code=c[0], name_en=c[1], name_hi=c[2], name_kn=c[3], category=c[4], emoji=c[5],
             agmarknet_name=c[6], perishability_k=c[7], storage_cost_per_qtl_day=c[8])
        for c in CROPS
    ], ["code"])
    upsert(db, Mandi, [
        dict(code=m[0], name=m[1], district=m[2], agmarknet_name=m[3], lat=m[4], lon=m[5],
             market_fee_pct=m[6], commission_pct=m[7], hamali_per_qtl=m[8])
        for m in MANDIS
    ], ["code"])
    db.flush()
    crop_ids = dict(db.execute(select(Crop.code, Crop.id)).all())
    msp_rows = []
    for code, table in MSP.items():
        last = max(table)
        for y, p in table.items():
            msp_rows.append(dict(crop_id=crop_ids[code], season_year=y, price=p, is_estimate=False))
        msp_rows.append(dict(crop_id=crop_ids[code], season_year=last + 1,
                             price=round(table[last] * (1 + MSP_ESTIMATE_GROWTH)), is_estimate=True))
    upsert(db, Msp, msp_rows, ["crop_id", "season_year"])
    ev = [dict(date=d, name=n, kind="festival", demand_impact=i)
          for d, n, i in synthetic.festival_dates(date(2022, 1, 1), date(2028, 12, 31))]
    upsert(db, CalendarEvent, ev, ["date", "name"])
    db.commit()


def _ids(db: Session):
    crops = dict(db.execute(select(Crop.code, Crop.id)).all())
    mandis = dict(db.execute(select(Mandi.code, Mandi.id)).all())
    return crops, mandis


def _start_run(db: Session, source: str) -> IngestionRun:
    run = IngestionRun(source=source)
    db.add(run)
    db.flush()
    return run


def _finish_run(db: Session, run: IngestionRun, report: dict, upserted: int, imputed: int = 0, status="ok"):
    run.finished_at = datetime.now(UTC)
    run.rows_in = int(report.get("rows_in", 0))
    run.rows_rejected = int(report.get("rows_rejected", 0))
    run.rows_upserted = int(upserted)
    run.rows_imputed = int(imputed)
    run.details = {k: int(v) for k, v in report.items()}
    run.status = status
    db.commit()


def ingest_prices(db: Session, df: pd.DataFrame, source: str) -> IngestionRun:
    """df columns: crop_id, mandi_id, date, min/max/modal_price, arrivals_tonnes."""
    run = _start_run(db, f"prices:{source}")
    if df.empty:
        _finish_run(db, run, {"rows_in": 0}, 0, status="empty")
        return run
    lo = pd.to_datetime(df["date"]).min().date() - timedelta(days=10)
    hist = pd.read_sql(
        select(PriceHistory.crop_id, PriceHistory.mandi_id, PriceHistory.date, PriceHistory.modal_price)
        .where(PriceHistory.date >= lo, PriceHistory.is_imputed.is_(False)),
        db.connection(),
    )
    clean, report = check_prices(df, hist)
    now = datetime.now(UTC)
    rows = [
        dict(crop_id=int(r.crop_id), mandi_id=int(r.mandi_id), date=r.date, min_price=float(r.min_price),
             max_price=float(r.max_price), modal_price=float(r.modal_price),
             arrivals_tonnes=None if pd.isna(r.arrivals_tonnes) else float(r.arrivals_tonnes),
             source=source, is_imputed=False, ingested_at=now)
        for r in clean.itertuples()
    ]
    n = upsert(db, PriceHistory, rows, ["crop_id", "mandi_id", "date"])
    db.flush()
    imputed = impute_gaps(db, since=pd.to_datetime(df["date"]).min().date())
    _finish_run(db, run, report, n, imputed)
    return run


def impute_gaps(db: Session, since: date) -> int:
    """Forward-fill short gaps (<= 3 days) per series, flagged is_imputed. Never overwrites real rows."""
    df = pd.read_sql(
        select(PriceHistory.crop_id, PriceHistory.mandi_id, PriceHistory.date, PriceHistory.min_price,
               PriceHistory.max_price, PriceHistory.modal_price).where(PriceHistory.date >= since - timedelta(days=5)),
        db.connection(),
    )
    if df.empty:
        return 0
    df["date"] = pd.to_datetime(df["date"])
    rows = []
    for (c, m), g in df.groupby(["crop_id", "mandi_id"]):
        g = g.set_index("date").sort_index()
        full = g.reindex(pd.date_range(g.index.min(), g.index.max(), freq="D"))
        missing = full["modal_price"].isna()
        if not missing.any():
            continue
        filled = full.ffill(limit=IMPUTE_MAX_GAP_DAYS)
        for d in full.index[missing & filled["modal_price"].notna()]:
            r = filled.loc[d]
            rows.append(dict(crop_id=int(c), mandi_id=int(m), date=d.date(), min_price=float(r.min_price),
                             max_price=float(r.max_price), modal_price=float(r.modal_price),
                             arrivals_tonnes=None, source="imputed", is_imputed=True))
    upsert(db, PriceHistory, rows, ["crop_id", "mandi_id", "date"], update_cols=[])  # do-nothing on conflict
    return len(rows)


def ingest_weather(db: Session, df: pd.DataFrame, source: str) -> IngestionRun:
    run = _start_run(db, f"weather:{source}")
    clean, report = check_weather(df)
    rows = [
        dict(mandi_id=int(r.mandi_id), date=r.date,
             **{c: (None if pd.isna(getattr(r, c)) else float(getattr(r, c)))
                for c in ["temp_max", "temp_min", "rain_mm", "humidity"]},
             is_forecast=bool(r.is_forecast), source=source)
        for r in clean.itertuples()
    ]
    n = upsert(db, Weather, rows, ["mandi_id", "date"])
    report["rows_rejected"] = report["rows_in"] - report["rows_clean"]
    _finish_run(db, run, report, n)
    return run


# ----- synthetic source -----------------------------------------------------------------------
def ingest_synthetic(db: Session, end: date | None = None, start: date | None = None) -> dict:
    """Generate (deterministically) and upsert synthetic weather + prices up to `end` (default: yesterday)."""
    end = end or date.today() - timedelta(days=1)
    start = start or synthetic.SYNTHETIC_START
    crops, mandis = _ids(db)
    w = synthetic.generate_weather(synthetic.SYNTHETIC_START, end)
    p = synthetic.generate_prices(synthetic.SYNTHETIC_START, end, w)
    w = w[w["date"] >= start].assign(mandi_id=lambda d: d["mandi"].map(mandis))
    p = p[p["date"] >= start].assign(crop_id=lambda d: d["crop"].map(crops), mandi_id=lambda d: d["mandi"].map(mandis))
    wr = ingest_weather(db, w, "synthetic")
    pr = ingest_prices(db, p, "synthetic")
    return {"weather_rows": wr.rows_upserted, "price_rows": pr.rows_upserted, "price_rejected": pr.rows_rejected,
            "price_imputed": pr.rows_imputed}


# ----- live sources ---------------------------------------------------------------------------
def ingest_live(db: Session) -> dict:
    """Pull Agmarknet + Open-Meteo. Raises on failure so callers can fall back."""
    crops, mandis = _ids(db)
    crop_by_ag = {c.agmarknet_name.lower(): c.id for c in db.scalars(select(Crop))}
    mandi_by_ag = {m.agmarknet_name.lower(): m.id for m in db.scalars(select(Mandi))}
    out = {}
    raw = sources.fetch_agmarknet()
    if not raw.empty:
        raw["crop_id"] = raw["commodity"].str.lower().map(crop_by_ag)
        raw["mandi_id"] = raw["market"].str.lower().map(mandi_by_ag)
        known = raw.dropna(subset=["crop_id", "mandi_id"])
        out["agmarknet_unmapped"] = int(len(raw) - len(known))
        out["prices"] = ingest_prices(db, known, "agmarknet").rows_upserted
    frames = []
    for m in db.scalars(select(Mandi)):
        f = sources.fetch_open_meteo(m.lat, m.lon)
        frames.append(f.assign(mandi_id=m.id))
    out["weather"] = ingest_weather(db, pd.concat(frames), "open-meteo").rows_upserted
    return out


def run_scheduled_ingestion(db: Session) -> dict:
    """Daily job. Live APIs if configured, otherwise extend the synthetic series. Always idempotent."""
    s = get_settings()
    if s.use_live_apis:
        try:
            return {"mode": "live", **ingest_live(db)}
        except Exception as e:  # network/key failure -> synthetic fallback
            db.rollback()
            log.warning("live ingestion failed (%s); falling back to synthetic", e)
    last = db.scalar(select(func.max(PriceHistory.date)))
    start = (last - timedelta(days=7)) if last else None
    return {"mode": "synthetic", **ingest_synthetic(db, start=start)}
