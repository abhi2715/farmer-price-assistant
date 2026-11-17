"""The three candidate forecasters. All predict log-return y = lp[t+h] - lp[t] from an origin row."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from agriroute_ml.features import CAT_FEATURES, FEATURES, to_matrix

log = logging.getLogger(__name__)
for noisy in ("cmdstanpy", "prophet"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


class SeasonalNaive:
    """Level-adjusted seasonal naive: apply last year's move over the same calendar window."""

    name = "seasonal_naive"

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        return rows["seas_prior"].fillna(0.0).to_numpy()


class LGBMForecaster:
    """Global direct multi-horizon LightGBM over all crop x mandi series (horizon is a feature)."""

    name = "lightgbm"
    params = dict(
        objective="huber", alpha=0.9, learning_rate=0.05, num_leaves=63, min_data_in_leaf=100,
        feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1,
        seed=7, num_threads=max(1, (os.cpu_count() or 2) - 1),
    )

    def __init__(self, num_boost_round: int = 400):
        self.num_boost_round = num_boost_round
        self.booster = None
        self.categories: dict[str, list[str]] = {}

    def fit(self, rows: pd.DataFrame) -> LGBMForecaster:
        import lightgbm as lgb

        self.categories = {c: sorted(rows[c].unique()) for c in CAT_FEATURES}
        X = to_matrix(rows, self.categories)
        ds = lgb.Dataset(X, rows["y"].to_numpy(), categorical_feature=CAT_FEATURES, free_raw_data=True)
        self.booster = lgb.train(self.params, ds, num_boost_round=self.num_boost_round)
        return self

    def matrix(self, rows: pd.DataFrame) -> pd.DataFrame:
        return to_matrix(rows, self.categories)

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(self.matrix(rows))

    def feature_importance(self) -> dict[str, float]:
        gain = self.booster.feature_importance("gain")
        return dict(sorted(zip(FEATURES, (float(g) for g in gain)), key=lambda kv: -kv[1]))


class ProphetForecaster:
    """Per-series Prophet on log price with festival holidays and yearly seasonality."""

    name = "prophet"

    def __init__(self, events: pd.DataFrame):
        hol = pd.DataFrame({"holiday": "festival", "ds": pd.to_datetime(events["date"]),
                            "lower_window": -10, "upper_window": 2})
        self.holidays = hol

    def _fit_series(self, hist: pd.DataFrame):
        from prophet import Prophet

        _ensure_cmdstan()
        m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                    holidays=self.holidays, uncertainty_samples=0, changepoint_prior_scale=0.1)
        df = pd.DataFrame({"ds": hist["date"], "y": hist["lp"]})
        with _quiet():
            m.fit(df)
        return m

    def predict_series(self, hist: pd.DataFrame, origin_lp: float, horizons: list[int]) -> np.ndarray:
        """hist: observed rows of one series up to origin (columns date, lp)."""
        m = self._fit_series(hist)
        origin = pd.Timestamp(hist["date"].max())
        fut = pd.DataFrame({"ds": [origin + pd.Timedelta(days=h) for h in horizons]})
        yhat = m.predict(fut)["yhat"].to_numpy()
        return yhat - origin_lp


class _quiet:
    def __enter__(self):
        self._fd = os.dup(2)
        self._null = os.open(os.devnull, os.O_WRONLY)
        sys.stderr.flush()
        os.dup2(self._null, 2)

    def __exit__(self, *a):
        os.dup2(self._fd, 2)
        os.close(self._null)
        os.close(self._fd)


def _ensure_cmdstan() -> None:
    """Prophet wheels bundle CmdStan without the `makefile` that newer cmdstanpy validates for."""
    import prophet

    for d in (Path(prophet.__file__).parent / "stan_model").glob("cmdstan-*"):
        mk = d / "makefile"
        if not mk.exists():
            try:
                mk.touch()
            except OSError:  # read-only site-packages: nothing we can do, prophet_available() reports it
                pass


def prophet_available() -> bool:
    try:
        _ensure_cmdstan()
        from prophet import Prophet

        Prophet()
        return True
    except Exception as e:  # pragma: no cover - environment dependent
        log.warning("Prophet unavailable: %s", e)
        return False
