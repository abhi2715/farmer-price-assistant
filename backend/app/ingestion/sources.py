"""Clients for live data: Agmarknet (via data.gov.in) and Open-Meteo.

Both return DataFrames in the internal shape; callers fall back to synthetic data on any error.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import httpx
import pandas as pd

from app.config import get_settings

log = logging.getLogger(__name__)
DATAGOV_URL = "https://api.data.gov.in/resource/{rid}"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def fetch_agmarknet(state: str = "Karnataka", limit: int = 5000, timeout: float = 30.0) -> pd.DataFrame:
    """Today's mandi prices for a state. Columns: commodity, market, date, min/max/modal price."""
    s = get_settings()
    if not s.datagov_api_key:
        raise RuntimeError("DATAGOV_API_KEY not set")
    params = {"api-key": s.datagov_api_key, "format": "json", "limit": limit, "filters[state.keyword]": state}
    r = httpx.get(DATAGOV_URL.format(rid=s.agmarknet_resource_id), params=params, timeout=timeout)
    r.raise_for_status()
    records = r.json().get("records", [])
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df = df.rename(columns={"min_price": "min_price", "max_price": "max_price", "modal_price": "modal_price"})
    df["date"] = df["arrival_date"].map(lambda v: datetime.strptime(v, "%d/%m/%Y").date())
    # The daily feed has no arrivals column; leave NaN (feature builder handles it).
    df["arrivals_tonnes"] = pd.to_numeric(df.get("arrivals_tonnes"), errors="coerce") if "arrivals_tonnes" in df else None
    return df[["commodity", "market", "date", "min_price", "max_price", "modal_price", "arrivals_tonnes"]]


def fetch_open_meteo(lat: float, lon: float, start: date | None = None, end: date | None = None,
                     forecast_days: int = 16, timeout: float = 20.0) -> pd.DataFrame:
    """Daily weather. With start/end -> archive API; otherwise past 7 days + 16-day forecast."""
    daily = "temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean"
    if start and end:
        url, params = OPEN_METEO_ARCHIVE, {"start_date": start.isoformat(), "end_date": end.isoformat()}
    else:
        url, params = OPEN_METEO_FORECAST, {"past_days": 7, "forecast_days": forecast_days}
    params |= {"latitude": lat, "longitude": lon, "daily": daily, "timezone": "Asia/Kolkata"}
    r = httpx.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    d = r.json()["daily"]
    df = pd.DataFrame({
        "date": pd.to_datetime(d["time"]).date,
        "temp_max": d["temperature_2m_max"],
        "temp_min": d["temperature_2m_min"],
        "rain_mm": d["precipitation_sum"],
        "humidity": d.get("relative_humidity_2m_mean"),
    })
    df["is_forecast"] = df["date"] > date.today()
    return df
