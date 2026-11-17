"""Load the active model, produce 1..30-day forecasts with conformal intervals, explain with SHAP."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from agriroute_ml.features import FEATURES, horizon_frame
from agriroute_ml.models import LGBMForecaster, ProphetForecaster, SeasonalNaive, prophet_available

log = logging.getLogger(__name__)


@dataclass
class ActiveModel:
    version: str
    best_model: str
    lgbm: LGBMForecaster
    intervals: dict  # model -> {h: [q_lo, q_hi]}
    meta: dict = field(default_factory=dict)
    _explainer: object = None

    def interval(self, model: str, h: int) -> tuple[float, float]:
        raw = self.intervals.get(model) or self.intervals["lightgbm"]
        table = {int(k): v for k, v in raw.items()}
        hs = sorted(table)
        lo = np.interp(h, hs, [table[k][0] for k in hs])
        hi = np.interp(h, hs, [table[k][1] for k in hs])
        return float(lo), float(hi)

    # ---- explainability ----
    def shap_values(self, rows: pd.DataFrame) -> np.ndarray:
        """TreeSHAP contributions (n_rows x n_features) in log-return space."""
        X = self.lgbm.matrix(rows)
        try:
            import shap

            if self._explainer is None:
                self._explainer = shap.TreeExplainer(self.lgbm.booster)
            return np.asarray(self._explainer.shap_values(X))
        except Exception as e:  # shap can't parse some categorical splits -> LightGBM's native TreeSHAP
            log.debug("shap.TreeExplainer unavailable (%s); using pred_contrib", e)
            return self.lgbm.booster.predict(X, pred_contrib=True)[:, : len(FEATURES)]


def load_active(model_dir: str) -> ActiveModel | None:
    reg = Path(model_dir) / "registry.json"
    if not reg.exists():
        return None
    import lightgbm as lgb

    r = json.loads(reg.read_text())
    d = Path(model_dir) / r["active"]
    meta = json.loads((d / "meta.json").read_text())
    m = LGBMForecaster()
    m.booster = lgb.Booster(model_file=str(d / "lgbm.txt"))
    m.categories = meta["categories"]
    return ActiveModel(version=r["active"], best_model=r["best_model"], lgbm=m,
                       intervals=json.loads((d / "intervals.json").read_text()), meta=meta)


def forecast_latest(panel: pd.DataFrame, events: pd.DataFrame, model: ActiveModel, max_h: int = 30,
                    use_model: str | None = None) -> pd.DataFrame:
    """Forecast every series from its last date for h = 1..max_h."""
    name = use_model or model.best_model
    if name == "prophet" and not prophet_available():
        name = "lightgbm"
    last = panel.groupby(["crop", "mandi"])["date"].transform("max")
    origin_idx = panel.index[panel["date"] == last]
    # Only series the model knows (new crops/mandis wait for the next retrain).
    known = panel.loc[origin_idx, "crop"].isin(model.lgbm.categories["crop"]) & \
        panel.loc[origin_idx, "mandi"].isin(model.lgbm.categories["mandi"])
    origin_idx = origin_idx[known.to_numpy()]
    outs = []
    prophet_preds: dict[tuple, np.ndarray] = {}
    if name == "prophet":
        pf = ProphetForecaster(events)
        for i in origin_idx:
            c, m = panel.at[i, "crop"], panel.at[i, "mandi"]
            s = panel[(panel["crop"] == c) & (panel["mandi"] == m) & panel["observed"]]
            prophet_preds[(c, m)] = pf.predict_series(s[["date", "lp"]], float(panel.at[i, "lp"]), list(range(1, max_h + 1)))
    for h in range(1, max_h + 1):
        hf = horizon_frame(panel, h, events, with_target=False).loc[origin_idx]
        if name == "lightgbm":
            pred = model.lgbm.predict(hf)
        elif name == "seasonal_naive":
            pred = SeasonalNaive().predict(hf)
        else:
            pred = np.array([prophet_preds[(c, m)][h - 1] for c, m in zip(hf["crop"], hf["mandi"])])
        q_lo, q_hi = model.interval(name, h)
        lp_hat = hf["lp"].to_numpy() + pred
        outs.append(pd.DataFrame({
            "crop": hf["crop"].to_numpy(), "mandi": hf["mandi"].to_numpy(),
            "origin_date": pd.to_datetime(hf["date"]).dt.date.to_numpy(),
            "target_date": pd.to_datetime(hf["target_date"]).dt.date.to_numpy(), "horizon": h,
            "yhat": np.exp(lp_hat), "yhat_lo": np.exp(lp_hat + q_lo), "yhat_hi": np.exp(lp_hat + q_hi),
            "model_name": name, "model_version": model.version,
        }))
    return pd.concat(outs, ignore_index=True)
