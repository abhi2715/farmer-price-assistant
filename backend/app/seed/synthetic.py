"""Realistic synthetic mandi prices, arrivals and weather.

Used as the out-of-the-box fallback when data.gov.in / Open-Meteo are unavailable. The generator
is deterministic (seeded) and encodes the structure the forecasters should learn:
  * crop seasonality (harvest-glut lows) and yearly inflation drift
  * festival demand bumps ramping up before each festival
  * mean-reverting AR(1) shocks at state and mandi level
  * arrivals that move inversely with price
  * heavy-rain supply disruptions that lift perishable prices a few days later
  * an MSP soft floor for MSP crops
It also injects real-world mess: missing days, Sunday closures and rare data-entry outliers,
so the ingestion data-quality checks have something to do.
"""
from __future__ import annotations

import zlib
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.seed.reference_data import (
    CROP_ARRIVALS,
    CROP_SEASON,
    CROP_VOL,
    CROPS,
    FESTIVALS,
    MANDI_CROPS,
    MANDIS,
    MSP,
    MSP_ESTIMATE_GROWTH,
)

PERISHABLE = {"tomato", "green_chilli", "banana"}
SYNTHETIC_START = date(2023, 1, 1)  # fixed so regenerating with a later end date only appends


def _rng(seed: int, *keys: str) -> np.random.Generator:
    """One independent stream per (series, purpose): each stream draws a single array, so a longer
    date range reproduces the same prefix -> re-running ingestion is idempotent."""
    return np.random.default_rng([seed, zlib.crc32("|".join(keys).encode())])


def festival_dates(start: date, end: date) -> list[tuple[date, str, float]]:
    out = []
    for name, impact, by_year in FESTIVALS:
        for y, md in by_year.items():
            d = date.fromisoformat(f"{y}-{md}")
            if start <= d <= end:
                out.append((d, name, impact))
    return sorted(out)


def msp_for(crop: str, d: date) -> float | None:
    table = MSP.get(crop)
    if not table:
        return None
    year = d.year if d.month >= 10 else d.year - 1  # kharif marketing year starts Oct
    if year in table:
        return float(table[year])
    last = max(table)
    return float(table[last] * (1 + MSP_ESTIMATE_GROWTH) ** (year - last)) if year > last else float(table[min(table)])


def generate_weather(start: date, end: date, seed: int = 7, forecast_days: int = 16) -> pd.DataFrame:
    days = pd.date_range(start, end + timedelta(days=forecast_days), freq="D")
    doy = days.dayofyear.to_numpy()
    month = days.month.to_numpy()
    rows = []
    # Monsoon rain probability by month (Karnataka, rough climatology)
    p_rain = np.array([0.03, 0.03, 0.06, 0.15, 0.30, 0.55, 0.65, 0.62, 0.50, 0.40, 0.20, 0.06])
    for code, _name, _d, _a, lat, lon, *_ in MANDIS:
        north = (lat - 12.0) / 6.0  # 0 south .. 1 north: hotter & drier
        coastal_wet = max(0.0, (76.2 - lon)) * 0.6  # western ghats side is wetter
        tmax = 30 + 3 * north + 4.0 * np.sin(2 * np.pi * (doy - 30) / 365) - 2.5 * ((month >= 6) & (month <= 9))
        tmax = tmax + _rng(seed, code, "tmax").normal(0, 1.2, len(days))
        tmin = tmax - 10 + _rng(seed, code, "tmin").normal(0, 1.0, len(days))
        pr = np.clip(p_rain[month - 1] * (1 - 0.25 * north + coastal_wet), 0, 0.95)
        is_rain = _rng(seed, code, "rainday").random(len(days)) < pr
        amount = _rng(seed, code, "rainamt").gamma(1.4, 9 * (1 + coastal_wet), len(days))
        rain = np.where(is_rain, amount, 0.0)
        hum = np.clip(55 + 30 * pr + _rng(seed, code, "hum").normal(0, 5, len(days)), 20, 100)
        for i, d in enumerate(days):
            rows.append(
                (code, d.date(), round(float(tmax[i]), 1), round(float(tmin[i]), 1), round(float(rain[i]), 1),
                 round(float(hum[i]), 0), d.date() > end)
            )
    return pd.DataFrame(rows, columns=["mandi", "date", "temp_max", "temp_min", "rain_mm", "humidity", "is_forecast"])


def generate_prices(start: date, end: date, weather: pd.DataFrame, seed: int = 42, mess: bool = True) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="D")
    n = len(days)
    doy = days.dayofyear.to_numpy()
    t_years = (days - days[0]).days.to_numpy() / 365.0

    # Festival ramp: effect builds over 10 days before festival, fades 2 days after.
    fest = np.zeros(n)
    for d, _name, impact in festival_dates(start - timedelta(days=15), end + timedelta(days=15)):
        delta = (days - pd.Timestamp(d)).days.to_numpy()
        ramp = np.where((delta >= -10) & (delta <= 0), (10 + delta) / 10, 0) + np.where((delta > 0) & (delta <= 2), 0.5, 0)
        fest = np.maximum(fest, impact * ramp)

    w = weather[~weather["is_forecast"]].copy()
    w["date"] = pd.to_datetime(w["date"])
    state_rain = w.groupby("date")["rain_mm"].mean().reindex(days).fillna(0).to_numpy()
    rain7 = pd.Series(state_rain).rolling(7, min_periods=1).sum().to_numpy()
    rain_shock = np.roll(np.clip(rain7 - 45, 0, None), 4) * 0.003  # lagged supply disruption
    rain_shock[:4] = 0

    out = []
    crop_meta = {c[0]: c for c in CROPS}
    for crop, (low_month, amp) in CROP_SEASON.items():
        base = crop_meta[crop][9]
        vol = CROP_VOL[crop]
        phi = 0.96 if crop in PERISHABLE or crop in {"onion", "potato"} else 0.985
        low_doy = (low_month - 1) * 30.5 + 15
        season = -amp * np.cos(2 * np.pi * (doy - low_doy) / 365)
        sens = 1.0 if crop in PERISHABLE | {"onion", "potato"} else 0.35
        # AR(1) state shock
        eps = _rng(seed, crop, "eps").normal(0, vol, n)
        x = np.zeros(n)
        for i in range(1, n):
            x[i] = phi * x[i - 1] + eps[i]
        state_log = np.log(base) + 0.05 * t_years + season + sens * fest + x
        if crop in PERISHABLE:
            state_log += rain_shock
        if crop in MSP:
            floor = np.log(np.array([msp_for(crop, d.date()) for d in days]) * 0.93)
            state_log = np.where(state_log < floor, floor + 0.3 * (state_log - floor), state_log)
        harvest = 1 + 0.6 * np.cos(2 * np.pi * (doy - low_doy) / 365)  # arrivals peak at harvest

        for mandi, crops in MANDI_CROPS.items():
            if crop not in crops:
                continue
            prem = crops[crop]
            size = 1.0 if mandi in {"blr_ypr", "kolar", "hubballi"} else _rng(seed, crop, mandi, "size").uniform(0.3, 0.7)
            m_eps = _rng(seed, crop, mandi, "eps").normal(0, vol * 0.5, n)
            mx = np.zeros(n)
            for i in range(1, n):
                mx[i] = 0.85 * mx[i - 1] + m_eps[i]
            a_shock = _rng(seed, crop, mandi, "arr").normal(0, 0.25, n)
            arrivals = CROP_ARRIVALS[crop] * size * harvest * np.exp(a_shock)
            log_p = state_log + prem + mx - 0.08 * a_shock
            modal = np.exp(log_p)
            spread_lo = _rng(seed, crop, mandi, "lo").uniform(0.08, 0.2, n)
            spread_hi = _rng(seed, crop, mandi, "hi").uniform(0.05, 0.15, n)
            df = pd.DataFrame({
                "crop": crop, "mandi": mandi, "date": days.date,
                "modal_price": np.round(modal, 0),
                "min_price": np.round(modal * (1 - spread_lo), 0),
                "max_price": np.round(modal * (1 + spread_hi), 0),
                "arrivals_tonnes": np.round(arrivals, 1),
            })
            if mess:
                keep = _rng(seed, crop, mandi, "gap").random(n) > 0.03  # random gaps
                if mandi in {"kalaburagi", "raichur", "hassan"}:
                    keep &= days.dayofweek.to_numpy() != 6  # Sunday closures
                bad = _rng(seed, crop, mandi, "bad").random(n) < 0.001  # fat-finger outliers (x10)
                df.loc[bad, "modal_price"] *= 10
                df = df[keep].copy()
            out.append(df)
    return pd.concat(out, ignore_index=True)


# ----- demo marketplace actors ---------------------------------------------------------------
DEMO_FARMERS = [
    # phone, name, village, district, lat, lon, language, crops
    ("9000000001", "Ramesh Gowda", "Srinivaspur", "Kolar", 13.338, 78.213, "kn", ["tomato", "green_chilli", "ragi"]),
    ("9000000002", "Lakshmi Devi", "Gauribidanur", "Chikkaballapur", 13.613, 77.517, "kn", ["tomato", "potato", "maize"]),
    ("9000000003", "Suresh Patil", "Kundgol", "Dharwad", 15.256, 75.248, "hi", ["onion", "cotton", "maize"]),
    ("9000000004", "Manjunath H", "Nanjangud", "Mysuru", 12.120, 76.680, "en", ["banana", "paddy", "tomato"]),
    ("9000000005", "Basavaraj K", "Aland", "Kalaburagi", 17.565, 76.568, "hi", ["tur", "cotton"]),
]
DEMO_BUYERS = [
    # phone, name, business, type, district, lat, lon
    ("9100000001", "Anil Traders", "Anil Fresh Traders", "trader", "Bengaluru Urban", 12.990, 77.570),
    ("9100000002", "Priya Foods", "Priya Foods Pvt Ltd", "processor", "Bengaluru Rural", 13.200, 77.700),
    ("9100000003", "Deccan Agro", "Deccan Agro Exports", "exporter", "Dharwad", 15.400, 75.050),
    ("9100000004", "Mysore Mart", "Mysore Mart Retail", "retailer", "Mysuru", 12.300, 76.640),
]
# buyer phone, crop, min_grade, qty, price markup vs current state price, max km
DEMO_DEMANDS = [
    ("9100000001", "tomato", "B", 80, 1.15, 160),
    ("9100000001", "green_chilli", "B", 20, 1.12, 160),
    ("9100000002", "tomato", "A", 120, 1.10, 200),
    ("9100000002", "potato", "B", 60, 1.10, 200),
    ("9100000002", "ragi", "B", 100, 1.08, 200),
    ("9100000003", "onion", "B", 200, 1.10, 150),
    ("9100000003", "cotton", "B", 150, 1.06, 300),
    ("9100000003", "maize", "C", 200, 1.08, 200),
    ("9100000004", "banana", "B", 40, 1.12, 120),
    ("9100000004", "paddy", "B", 150, 1.07, 150),
    ("9100000004", "tomato", "B", 30, 1.15, 120),
    ("9100000003", "tur", "B", 80, 1.08, 400),
]
ADMIN_PHONE = "9999999999"
