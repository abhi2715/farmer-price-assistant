"""Data-quality checks for mandi price batches.

Each check either repairs a row (and counts it) or rejects it with a reason. Returned stats are
stored on the IngestionRun row so the admin view can show data health.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

REQUIRED = ["crop_id", "mandi_id", "date", "modal_price"]
OUTLIER_LOG_RATIO = float(np.log(2.5))  # >2.5x away from the local median => reject


def check_prices(batch: pd.DataFrame, history: pd.DataFrame | None = None, today: date | None = None):
    """Return (clean_df, report). `history` = recent stored rows for robust outlier baselines."""
    today = today or date.today()
    report: dict[str, int] = {"rows_in": len(batch)}
    df = batch.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    def reject(mask: pd.Series, reason: str) -> None:
        nonlocal df
        report[f"rejected_{reason}"] = int(mask.sum())
        df = df[~mask]

    reject(df[REQUIRED].isna().any(axis=1), "missing_fields")
    for c in ["modal_price", "min_price", "max_price", "arrivals_tonnes"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    reject(~(df["modal_price"] > 0), "non_positive")
    reject(df["date"] > today, "future_date")

    # Fill missing min/max from modal; swap inverted min/max; widen band to contain modal.
    df["min_price"] = df.get("min_price", df["modal_price"]).fillna(df["modal_price"])
    df["max_price"] = df.get("max_price", df["modal_price"]).fillna(df["modal_price"])
    inverted = df["min_price"] > df["max_price"]
    report["repaired_inverted_minmax"] = int(inverted.sum())
    df.loc[inverted, ["min_price", "max_price"]] = df.loc[inverted, ["max_price", "min_price"]].to_numpy()
    out_band = (df["modal_price"] < df["min_price"]) | (df["modal_price"] > df["max_price"])
    report["repaired_modal_out_of_band"] = int(out_band.sum())
    df["min_price"] = np.minimum(df["min_price"], df["modal_price"])
    df["max_price"] = np.maximum(df["max_price"], df["modal_price"])
    if "arrivals_tonnes" in df:
        neg = df["arrivals_tonnes"] < 0
        df.loc[neg, "arrivals_tonnes"] = np.nan
        report["repaired_negative_arrivals"] = int(neg.sum())

    before = len(df)
    df = df.drop_duplicates(subset=["crop_id", "mandi_id", "date"], keep="last")
    report["dropped_duplicates"] = before - len(df)

    # Robust outlier check: compare against a centred rolling median of the same series
    # (stored history + this batch), so x10 typos are caught but real moves are kept.
    key = ["crop_id", "mandi_id"]
    ctx = df[key + ["date", "modal_price"]].assign(_new=True)
    if history is not None and len(history):
        h = history[key + ["date", "modal_price"]].copy()
        h["date"] = pd.to_datetime(h["date"]).dt.date
        ctx = pd.concat([h.assign(_new=False), ctx], ignore_index=True)
        ctx = ctx.drop_duplicates(subset=key + ["date"], keep="last")
    ctx = ctx.sort_values(key + ["date"])
    ctx["_med"] = ctx.groupby(key)["modal_price"].transform(
        lambda s: s.rolling(15, center=True, min_periods=3).median()
    )
    ctx = ctx[ctx["_new"]].set_index(key + ["date"])
    med = df.set_index(key + ["date"]).index.map(ctx["_med"].to_dict())
    ratio = np.abs(np.log(df["modal_price"].to_numpy() / np.asarray(med, dtype=float)))
    outlier = pd.Series(np.nan_to_num(ratio, nan=0.0) > OUTLIER_LOG_RATIO, index=df.index)
    reject(outlier, "outlier")

    report["rows_clean"] = len(df)
    report["rows_rejected"] = report["rows_in"] - len(df)
    return df.reset_index(drop=True), report


def check_weather(batch: pd.DataFrame):
    df = batch.copy()
    report = {"rows_in": len(df)}
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for c, lo, hi in [("temp_max", -5, 52), ("temp_min", -10, 40), ("rain_mm", 0, 500), ("humidity", 0, 100)]:
        if c in df:
            bad = (df[c] < lo) | (df[c] > hi)
            report[f"nulled_{c}"] = int(bad.sum())
            df.loc[bad, c] = np.nan
    df = df.dropna(subset=["mandi_id", "date"]).drop_duplicates(subset=["mandi_id", "date"], keep="last")
    report["rows_clean"] = len(df)
    return df.reset_index(drop=True), report
