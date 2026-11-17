# agriroute_ml

A database-agnostic forecasting package used by the backend (`app/services/forecasting.py`).

| Module | What |
|---|---|
| `features.py` | Daily panel per crop × mandi, base and horizon features, leakage-safe training rows |
| `models.py` | `SeasonalNaive` (level-adjusted yearly), `ProphetForecaster` (per series, festival holidays), `LGBMForecaster` (global, direct multi-horizon) |
| `train.py` | Rolling-origin backtest, fair-cell comparison, model selection, conformal residuals, final fit, report and MLflow logging |
| `forecast.py` | Load the active model, produce 1–30-day forecasts with intervals, TreeSHAP values |

Run training against the app database: `cd backend && .venv/bin/python -c "from app.db import SessionLocal; from app.services.forecasting import train; print(train(SessionLocal()))"`, or trigger the `train` job from the admin view.

Outputs:
- `reports/backtest_report.md` and `.json`: MAPE by model and horizon, MAPE by crop, feature importance.
- `$MODEL_DIR/<version>/`: `lgbm.txt`, `intervals.json`, `meta.json`.
- `$MODEL_DIR/registry.json`: the active version.
- MLflow experiment `agriroute-forecasting`.

On macOS without Homebrew, LightGBM needs `libomp`. Run `../scripts/fix-macos-libomp.sh`, which points LightGBM at the copy bundled with scikit-learn. Prophet's bundled CmdStan is patched at runtime (`_ensure_cmdstan`).
