"""Rolling-origin backtest of seasonal-naive vs Prophet vs LightGBM, model selection, final fit,
artifact + report writing and MLflow logging."""
from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from agriroute_ml.features import EVAL_HORIZONS, REPORT_HORIZONS, build_panel, horizon_frame, training_rows
from agriroute_ml.models import LGBMForecaster, ProphetForecaster, SeasonalNaive, prophet_available

log = logging.getLogger(__name__)
INTERVAL_Q = (0.1, 0.9)  # 80% prediction interval


def _mape(pred_lp, actual_lp) -> float:
    return float(np.mean(np.abs(np.exp(np.asarray(pred_lp) - np.asarray(actual_lp)) - 1)) * 100)


def backtest(panel: pd.DataFrame, events: pd.DataFrame, n_origins: int = 4, step: int = 28, n_series: int = 24,
             enable_prophet: bool = True, num_boost_round: int = 300, seed: int = 11) -> pd.DataFrame:
    last = panel["date"].max()
    origins = [last - pd.Timedelta(days=30 + k * step) for k in range(n_origins)]
    series = panel[["crop", "mandi"]].drop_duplicates().sort_values(["crop", "mandi"]).to_records(index=False).tolist()
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(series), size=min(n_series, len(series)), replace=False)
    subset = {tuple(series[i]) for i in pick}
    all_rows = training_rows(panel, events)
    hfs = {h: horizon_frame(panel, h, events) for h in EVAL_HORIZONS}
    naive = SeasonalNaive()
    prophet = ProphetForecaster(events) if enable_prophet else None
    recs = []
    for o in origins:
        t0 = time.time()
        lgbm = LGBMForecaster(num_boost_round).fit(all_rows[all_rows["target_date"] <= o])
        for h, hf in hfs.items():
            v = hf[(hf["date"] == o) & hf["target_observed"] & hf["y"].notna()]
            if v.empty:
                continue
            actual = (v["lp"] + v["y"]).to_numpy()
            base = dict(origin=o, h=h)
            for name, pred in (("lightgbm", lgbm.predict(v)), ("seasonal_naive", naive.predict(v))):
                for (c, m), lp0, p, a in zip(zip(v["crop"], v["mandi"]), v["lp"], pred, actual):
                    recs.append(dict(base, model=name, crop=c, mandi=m, pred_lp=lp0 + p, actual_lp=a,
                                     in_subset=(c, m) in subset))
        if prophet:
            for c, m in subset:
                s = panel[(panel["crop"] == c) & (panel["mandi"] == m)]
                hist = s[(s["date"] <= o) & s["observed"]]
                at_o = s[s["date"] == o]
                if len(hist) < 200 or at_o.empty:
                    continue
                lp0 = float(at_o["lp"].iloc[0])
                preds = prophet.predict_series(hist[["date", "lp"]], lp0, EVAL_HORIZONS)
                for h, p in zip(EVAL_HORIZONS, preds):
                    hv = hfs[h]
                    row = hv[(hv["date"] == o) & (hv["crop"] == c) & (hv["mandi"] == m) & hv["target_observed"]]
                    if row.empty or row["y"].isna().all():
                        continue
                    recs.append(dict(origin=o, h=h, model="prophet", crop=c, mandi=m, pred_lp=lp0 + p,
                                     actual_lp=float(lp0 + row["y"].iloc[0]), in_subset=True))
        log.info("backtest origin %s done in %.1fs", o.date(), time.time() - t0)
    return pd.DataFrame(recs)


def summarize(bt: pd.DataFrame) -> dict:
    """MAPE tables, model selection, and residual quantiles for conformal intervals."""
    sub = bt[bt["in_subset"]]
    models = sorted(sub["model"].unique())
    # Fair comparison: identical (series, origin, horizon) cells for every model.
    key = ["crop", "mandi", "origin", "h"]
    common = sub.groupby(key)["model"].nunique()
    common = common[common == len(models)].index
    sub = sub.set_index(key).loc[common].reset_index()
    by_h = {m: {int(h): _mape(g["pred_lp"], g["actual_lp"]) for h, g in sub[sub["model"] == m].groupby("h")}
            for m in models}
    overall = {m: float(np.mean([by_h[m][h] for h in REPORT_HORIZONS if h in by_h[m]])) for m in models}
    best = min(overall, key=overall.get)
    full = {m: {int(h): _mape(g["pred_lp"], g["actual_lp"]) for h, g in bt[bt["model"] == m].groupby("h")}
            for m in ("lightgbm", "seasonal_naive")}
    by_crop = {
        m: {c: _mape(g["pred_lp"], g["actual_lp"]) for c, g in bt[(bt["model"] == m) & bt["h"].isin(REPORT_HORIZONS)].groupby("crop")}
        for m in bt["model"].unique()
    }
    resid = {}
    for m, g in bt.groupby("model"):
        r = {}
        for h, gh in g.groupby("h"):
            e = gh["actual_lp"] - gh["pred_lp"]
            r[int(h)] = [float(e.quantile(INTERVAL_Q[0])), float(e.quantile(INTERVAL_Q[1]))]
        resid[m] = r
    return dict(models=models, mape_by_horizon=by_h, mape_overall=overall, best_model=best,
                mape_all_series=full, mape_by_crop=by_crop, residual_quantiles=resid,
                n_eval_cells=int(len(common)), n_origins=int(bt["origin"].nunique()))


def write_report(summary: dict, meta: dict, importance: dict, path: Path) -> None:
    hs = REPORT_HORIZONS
    lines = [
        "# AgriRoute forecasting backtest report", "",
        f"*Generated {meta['created_at']} - model version `{meta['version']}`*", "",
        "## Setup",
        f"- Data: {meta['n_series']} crop x mandi series, {meta['start']} to {meta['end']} ({meta['n_rows']:,} daily rows)",
        f"- Rolling-origin backtest: {summary['n_origins']} origins, 28 days apart, horizons {EVAL_HORIZONS} days",
        f"- Fair comparison on {summary['n_eval_cells']} identical (series, origin, horizon) cells "
        f"({meta['n_subset']} sampled series; Prophet is fit per series so it is evaluated on a sample)",
        "- Metric: MAPE of the modal price (Rs/quintal)", "",
        "## MAPE by horizon (%)", "",
        "| Model | " + " | ".join(f"{h}-day" for h in hs) + " | Mean |",
        "|---|" + "---|" * (len(hs) + 1),
    ]
    for m in summary["models"]:
        row = summary["mape_by_horizon"][m]
        star = " **(selected)**" if m == summary["best_model"] else ""
        lines.append(f"| {m}{star} | " + " | ".join(f"{row.get(h, float('nan')):.2f}" for h in hs)
                     + f" | {summary['mape_overall'][m]:.2f} |")
    lines += ["", "### All series (LightGBM vs seasonal naive)", "",
              "| Model | " + " | ".join(f"{h}-day" for h in hs) + " |", "|---|" + "---|" * len(hs)]
    for m, row in summary["mape_all_series"].items():
        lines.append(f"| {m} | " + " | ".join(f"{row.get(h, float('nan')):.2f}" for h in hs) + " |")
    best = summary["best_model"]
    lines += ["", f"## MAPE by crop - {best} (mean of 7/14/30-day)", "", "| Crop | MAPE % |", "|---|---|"]
    for c, v in sorted(summary["mape_by_crop"].get(best, {}).items(), key=lambda kv: kv[1]):
        lines.append(f"| {c} | {v:.2f} |")
    lines += ["", "## Selection", "",
              f"Selected **{best}**: lowest mean MAPE across 7/14/30-day horizons on the shared evaluation cells.",
              "Prediction intervals are 80% split-conformal intervals from backtest residuals (log space), per horizon.", "",
              "## LightGBM feature importance (gain, top 12)", "", "| Feature | Gain |", "|---|---|"]
    for f, g in list(importance.items())[:12]:
        lines.append(f"| {f} | {g:,.0f} |")
    path.write_text("\n".join(lines) + "\n")


def run_training(prices: pd.DataFrame, weather: pd.DataFrame, events: pd.DataFrame, msp: pd.DataFrame,
                 model_dir: str, report_dir: str, enable_prophet: bool = True, n_series: int = 24,
                 n_origins: int = 4, num_boost_round: int = 400, mlflow_uri: str = "") -> dict:
    t0 = time.time()
    enable_prophet = enable_prophet and prophet_available()
    panel = build_panel(prices, weather, events, msp)
    bt = backtest(panel, events, n_origins=n_origins, n_series=n_series, enable_prophet=enable_prophet,
                  num_boost_round=max(100, num_boost_round // 2))
    summary = summarize(bt)
    final = LGBMForecaster(num_boost_round).fit(training_rows(panel, events))
    version = datetime.now(UTC).strftime("v%Y%m%d%H%M%S")
    out = Path(model_dir) / version
    out.mkdir(parents=True, exist_ok=True)
    final.booster.save_model(str(out / "lgbm.txt"))
    importance = final.feature_importance()
    meta = dict(version=version, created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                best_model=summary["best_model"], categories=final.categories,
                n_series=int(panel[["crop", "mandi"]].drop_duplicates().shape[0]), n_subset=n_series,
                n_rows=int(len(panel)), start=str(panel["date"].min().date()), end=str(panel["date"].max().date()),
                prophet_enabled=enable_prophet, train_seconds=None)
    (out / "intervals.json").write_text(json.dumps(summary["residual_quantiles"]))
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    report_md = Path(report_dir) / "backtest_report.md"
    write_report(summary, meta, importance, report_md)
    meta["train_seconds"] = round(time.time() - t0, 1)
    metrics = {k: summary[k] for k in ("mape_by_horizon", "mape_overall", "best_model", "mape_all_series", "mape_by_crop")}
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    (Path(report_dir) / "backtest_report.json").write_text(json.dumps({"meta": meta, **metrics}, indent=2, default=str))
    (Path(model_dir) / "registry.json").write_text(json.dumps({"active": version, "best_model": summary["best_model"]}))
    _log_mlflow(mlflow_uri, model_dir, meta, summary, report_md, out)
    log.info("training done in %.1fs: best=%s %s", meta["train_seconds"], summary["best_model"], summary["mape_overall"])
    return dict(version=version, best_model=summary["best_model"], metrics=metrics, report_path=str(report_md),
                train_seconds=meta["train_seconds"])


def _log_mlflow(uri: str, model_dir: str, meta: dict, summary: dict, report: Path, art_dir: Path) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(uri or f"file:{Path(model_dir).resolve() / 'mlruns'}")
        mlflow.set_experiment("agriroute-forecasting")
        with mlflow.start_run(run_name=meta["version"]):
            mlflow.log_params({"best_model": meta["best_model"], "n_series": meta["n_series"],
                               "prophet_enabled": meta["prophet_enabled"], **LGBMForecaster.params})
            for m, row in summary["mape_by_horizon"].items():
                for h, v in row.items():
                    mlflow.log_metric(f"mape_{m}_h{h}", v)
                mlflow.log_metric(f"mape_{m}_mean", summary["mape_overall"][m])
            mlflow.log_artifact(str(report))
            mlflow.log_artifacts(str(art_dir), artifact_path="model")
    except Exception as e:  # MLflow is best-effort; never fail training because tracking is down
        log.warning("mlflow logging skipped: %s", e)
