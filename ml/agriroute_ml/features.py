"""Panel construction and feature engineering for direct multi-horizon forecasting.

Target: y = log(price[t+h]) - log(price[t])  (scale-free across crops, so one global model works).
All features use information available at origin t, plus the known future calendar (festivals,
day of year of the target date).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRAIN_HORIZONS = [1, 2, 3, 5, 7, 10, 14, 18, 21, 25, 30]
EVAL_HORIZONS = [1, 3, 7, 14, 21, 30]
REPORT_HORIZONS = [7, 14, 30]
CAT_FEATURES = ["crop", "mandi"]
BASE_FEATURES = [
    "r1", "r7", "r14", "r30", "vol14", "dev_ma7", "dev_ma30", "dev_ma90", "dev_ma365", "yoy",
    "arr_ratio", "arr_yoy", "rain7", "rain30", "tmax7", "msp_ratio", "fest_now", "days_to_fest",
]
H_FEATURES = ["h", "seas_prior", "target_doy_sin", "target_doy_cos", "fest_target", "fest_peak_in_window"]
FEATURES = CAT_FEATURES + BASE_FEATURES + H_FEATURES


def festival_effect(dates: pd.DatetimeIndex, events: pd.DataFrame) -> np.ndarray:
    """Demand-pressure curve: ramps up over the 10 days before a festival, lingers 2 days after."""
    eff = np.zeros(len(dates))
    for d, impact in zip(pd.to_datetime(events["date"]), events["demand_impact"]):
        delta = (dates - d).days.to_numpy()
        ramp = np.where((delta >= -10) & (delta <= 0), (10 + delta) / 10, 0) + np.where((delta > 0) & (delta <= 2), 0.5, 0)
        eff = np.maximum(eff, impact * ramp)
    return eff


def days_to_next(dates: pd.DatetimeIndex, events: pd.DataFrame, cap: int = 60) -> np.ndarray:
    ev = np.sort(pd.to_datetime(events["date"]).to_numpy())
    idx = np.searchsorted(ev, dates.to_numpy(), side="left")
    out = np.full(len(dates), float(cap))
    ok = idx < len(ev)
    out[ok] = np.minimum((ev[idx[ok]] - dates.to_numpy()[ok]).astype("timedelta64[D]").astype(float), cap)
    return out


def msp_lookup(msp: pd.DataFrame, crop: str, dates: pd.DatetimeIndex) -> np.ndarray:
    m = msp[msp["crop"] == crop]
    if m.empty:
        return np.full(len(dates), np.nan)
    table = dict(zip(m["season_year"], m["price"]))
    years = np.where(dates.month >= 10, dates.year, dates.year - 1)
    last = max(table)
    return np.array([table.get(y, table[last]) for y in years], dtype=float)


def build_panel(prices: pd.DataFrame, weather: pd.DataFrame, events: pd.DataFrame, msp: pd.DataFrame,
                end: pd.Timestamp | None = None) -> pd.DataFrame:
    """Daily grid per series with base features.

    prices: crop, mandi, date, modal_price, arrivals_tonnes, [is_imputed]
    weather: mandi, date, temp_max, rain_mm
    events: date, demand_impact
    msp: crop, season_year, price
    """
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    if "is_imputed" not in prices:
        prices["is_imputed"] = False
    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"])
    end = pd.Timestamp(end) if end is not None else prices["date"].max()
    frames = []
    for (crop, mandi), g in prices.groupby(["crop", "mandi"], sort=True):
        g = g.drop_duplicates("date").set_index("date").sort_index()
        idx = pd.date_range(g.index.min(), end, freq="D")
        g = g.reindex(idx)
        f = pd.DataFrame(index=idx)
        f["crop"], f["mandi"] = crop, mandi
        f["observed"] = g["modal_price"].notna() & ~g["is_imputed"].astype("boolean").fillna(False).astype(bool)
        price = g["modal_price"].ffill()
        f["price"] = price
        lp = np.log(price)
        f["lp"] = lp
        dlp = lp.diff()
        for k in (1, 7, 14, 30):
            f[f"r{k}"] = lp - lp.shift(k)
        f["vol14"] = dlp.rolling(14, min_periods=5).std()
        for k in (7, 30, 90, 365):
            f[f"dev_ma{k}"] = lp - lp.rolling(k, min_periods=max(3, k // 3)).mean()
        f["yoy"] = lp - lp.shift(365)
        arr = g["arrivals_tonnes"].astype(float)
        a7 = arr.rolling(7, min_periods=2).mean()
        f["arr_ratio"] = np.log(a7 / arr.rolling(60, min_periods=10).mean())
        f["arr_yoy"] = np.log(a7 / a7.shift(365))
        w = weather[weather["mandi"] == mandi].drop_duplicates("date").set_index("date").sort_index().reindex(idx)
        rain = w["rain_mm"].fillna(0)
        f["rain7"] = rain.rolling(7, min_periods=1).sum()
        f["rain30"] = rain.rolling(30, min_periods=1).sum()
        f["tmax7"] = w["temp_max"].rolling(7, min_periods=1).mean()
        f["msp_ratio"] = lp - np.log(msp_lookup(msp, crop, idx))
        frames.append(f)
    panel = pd.concat(frames)
    panel.index.name = "date"
    panel = panel.reset_index()
    dates = pd.DatetimeIndex(panel["date"])
    panel["fest_now"] = festival_effect(dates, events)
    panel["days_to_fest"] = days_to_next(dates, events)
    return panel


def horizon_frame(panel: pd.DataFrame, h: int, events: pd.DataFrame, with_target: bool = True) -> pd.DataFrame:
    """Rows of `panel` (origins) expanded with horizon-specific features (and target if available)."""
    p = panel
    g = p.groupby(["crop", "mandi"], sort=False)["lp"]
    out = p.copy()
    out["h"] = h
    # Last year's move over the same calendar window (level-adjusted seasonal prior).
    out["seas_prior"] = g.shift(365 - h) - g.shift(365)
    tgt = pd.DatetimeIndex(out["date"]) + pd.Timedelta(days=h)
    out["target_date"] = tgt
    doy = tgt.dayofyear.to_numpy()
    out["target_doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    out["target_doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    out["fest_target"] = festival_effect(tgt, events)
    out["fest_peak_in_window"] = (out["days_to_fest"] <= h).astype(float)
    if with_target:
        out["y"] = g.shift(-h) - p["lp"]
        out["target_observed"] = p.groupby(["crop", "mandi"], sort=False)["observed"].shift(-h).astype("boolean").fillna(False).astype(bool)
    return out


def training_rows(panel: pd.DataFrame, events: pd.DataFrame, horizons=TRAIN_HORIZONS, max_origin=None,
                  min_origin=None, stride: int = 2) -> pd.DataFrame:
    """Supervised rows with target known (t+h <= max_origin when given) and observed target."""
    frames = []
    base = panel[panel["observed"]]
    for h in horizons:
        hf = horizon_frame(panel, h, events)
        hf = hf.loc[base.index]
        hf = hf[hf["target_observed"] & hf["y"].notna()]
        if max_origin is not None:
            hf = hf[hf["target_date"] <= max_origin]
        if min_origin is not None:
            hf = hf[hf["date"] >= min_origin]
        if stride > 1:
            hf = hf[(hf["date"] - pd.Timestamp("2000-01-01")).dt.days % stride == 0]
        frames.append(hf)
    return pd.concat(frames, ignore_index=True)


def to_matrix(df: pd.DataFrame, categories: dict[str, list[str]] | None = None) -> pd.DataFrame:
    X = df[FEATURES].copy()
    for c in CAT_FEATURES:
        cats = categories[c] if categories else sorted(df[c].unique())
        X[c] = pd.Categorical(X[c], categories=cats)
    return X
