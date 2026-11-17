from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, select

from app.ingestion.pipeline import ingest_prices, run_scheduled_ingestion
from app.ingestion.quality import check_prices
from app.models import IngestionRun, PriceHistory
from app.seed import synthetic


def _batch(rows):
    return pd.DataFrame(rows, columns=["crop_id", "mandi_id", "date", "min_price", "max_price", "modal_price", "arrivals_tonnes"])


def test_quality_checks_reject_and_repair():
    d0 = date(2026, 1, 1)
    rows = [(1, 1, d0 + timedelta(days=i), 1800, 2200, 2000 + i, 10) for i in range(10)]
    rows += [
        (1, 1, d0 + timedelta(days=10), 1800, 2200, 20000, 10),   # x10 typo
        (1, 1, d0 + timedelta(days=11), 2300, 1900, 2100, 10),    # inverted min/max
        (1, 1, d0 + timedelta(days=12), 1800, 2200, -5, 10),      # non-positive
        (1, 1, date.today() + timedelta(days=5), 1800, 2200, 2000, 10),  # future
        (1, 1, d0, 1800, 2200, 2001, 10),                          # duplicate key
        (None, 1, d0, 1800, 2200, 2001, 10),                       # missing field
    ]
    clean, rep = check_prices(_batch(rows))
    assert rep["rejected_outlier"] == 1
    assert rep["rejected_non_positive"] == 1
    assert rep["rejected_future_date"] == 1
    assert rep["rejected_missing_fields"] == 1
    assert rep["repaired_inverted_minmax"] == 1
    assert rep["dropped_duplicates"] == 1
    assert (clean["min_price"] <= clean["modal_price"]).all() and (clean["modal_price"] <= clean["max_price"]).all()
    assert len(clean) == 11


def test_synthetic_generator_is_prefix_stable():
    end = date(2025, 6, 30)
    w = synthetic.generate_weather(synthetic.SYNTHETIC_START, end)
    a = synthetic.generate_prices(synthetic.SYNTHETIC_START, end, w)
    b = synthetic.generate_prices(synthetic.SYNTHETIC_START, end - timedelta(days=30), w)
    m = b.merge(a, on=["crop", "mandi", "date"], suffixes=("_b", "_a"))
    assert len(m) == len(b)
    assert np.allclose(m["modal_price_a"], m["modal_price_b"])


def test_ingestion_is_idempotent_and_imputes(db):
    before = db.scalar(select(func.count()).select_from(PriceHistory))
    run_scheduled_ingestion(db)
    run_scheduled_ingestion(db)
    assert db.scalar(select(func.count()).select_from(PriceHistory)) == before
    assert db.scalar(select(func.count()).select_from(PriceHistory).where(PriceHistory.is_imputed.is_(True))) > 0
    # Imputed rows only fill short gaps and never overwrite real data
    last = db.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()))
    assert last.status == "ok"


def test_ingest_rejects_bad_rows_into_run_report(db):
    d = date.today() - timedelta(days=400)
    run = ingest_prices(db, _batch([(1, 1, d, 1800, 2200, -1, 5)]), "test")
    assert run.rows_rejected == 1 and run.rows_upserted == 0


def test_training_selected_best_by_backtest(seeded):
    m = seeded["metrics"]
    assert seeded["best_model"] == min(m["mape_overall"], key=m["mape_overall"].get)
    assert {"lightgbm", "seasonal_naive"} <= set(m["mape_overall"])
    for model, row in m["mape_by_horizon"].items():
        assert all(0 < v < 100 for v in row.values()), model


def test_report_written(seeded):
    from pathlib import Path

    text = Path(seeded["report_path"]).read_text()
    assert "MAPE by horizon" in text and "7-day" in text and "30-day" in text


def test_features_do_not_leak_future():
    from agriroute_ml.features import BASE_FEATURES, build_panel, horizon_frame

    end = date(2025, 6, 30)
    w = synthetic.generate_weather(synthetic.SYNTHETIC_START, end)
    p = synthetic.generate_prices(synthetic.SYNTHETIC_START, end, w, mess=False)
    p = p[(p["crop"] == "tomato") & (p["mandi"] == "kolar")]
    ev = pd.DataFrame({"date": [date(2024, 10, 31)], "demand_impact": [0.1]})
    msp = pd.DataFrame(columns=["crop", "season_year", "price"])
    cut = pd.Timestamp(date(2025, 3, 1))
    a = horizon_frame(build_panel(p, w, ev, msp), 7, ev)
    p2 = p.copy()
    p2.loc[pd.to_datetime(p2["date"]) > cut, "modal_price"] *= 3  # change the future only
    b = horizon_frame(build_panel(p2, w, ev, msp), 7, ev)
    ra, rb = a[a["date"] == cut], b[b["date"] == cut]
    cols = BASE_FEATURES + ["seas_prior", "fest_target"]
    assert np.allclose(ra[cols].fillna(0).to_numpy(float), rb[cols].fillna(0).to_numpy(float))
    assert not np.isclose(ra["y"].iloc[0], rb["y"].iloc[0])  # the target does see the future
