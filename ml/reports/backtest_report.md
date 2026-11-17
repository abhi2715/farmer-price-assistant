# AgriRoute forecasting backtest report

*Generated 2026-11-17T09:27:30+00:00 - model version `v20261117092730`*

## Setup
- Data: 52 crop x mandi series, 2023-01-01 to 2026-11-16 (73,621 daily rows)
- Rolling-origin backtest: 4 origins, 28 days apart, horizons [1, 3, 7, 14, 21, 30] days
- Fair comparison on 545 identical (series, origin, horizon) cells (24 sampled series; Prophet is fit per series so it is evaluated on a sample)
- Metric: MAPE of the modal price (Rs/quintal)

## MAPE by horizon (%)

| Model | 7-day | 14-day | 30-day | Mean |
|---|---|---|---|---|
| lightgbm **(selected)** | 6.20 | 8.16 | 10.44 | 8.27 |
| prophet | 7.68 | 8.55 | 13.53 | 9.92 |
| seasonal_naive | 7.30 | 11.31 | 12.92 | 10.51 |

### All series (LightGBM vs seasonal naive)

| Model | 7-day | 14-day | 30-day |
|---|---|---|---|
| lightgbm | 5.50 | 6.48 | 8.33 |
| seasonal_naive | 6.87 | 9.14 | 11.21 |

## MAPE by crop - lightgbm (mean of 7/14/30-day)

| Crop | MAPE % |
|---|---|
| cotton | 2.48 |
| paddy | 2.54 |
| ragi | 2.70 |
| maize | 3.63 |
| tur | 3.69 |
| potato | 5.35 |
| banana | 7.04 |
| green_chilli | 9.49 |
| onion | 11.98 |
| tomato | 15.70 |

## Selection

Selected **lightgbm**: lowest mean MAPE across 7/14/30-day horizons on the shared evaluation cells.
Prediction intervals are 80% split-conformal intervals from backtest residuals (log space), per horizon.

## LightGBM feature importance (gain, top 12)

| Feature | Gain |
|---|---|
| dev_ma365 | 2,574 |
| target_doy_cos | 2,191 |
| crop | 1,991 |
| yoy | 1,904 |
| h | 1,613 |
| target_doy_sin | 1,438 |
| arr_ratio | 1,175 |
| seas_prior | 1,147 |
| dev_ma90 | 1,137 |
| r30 | 571 |
| dev_ma30 | 563 |
| days_to_fest | 519 |
