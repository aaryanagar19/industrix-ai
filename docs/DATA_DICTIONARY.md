# Data Dictionary

## Model features (accident-risk classifier)
| Feature | Unit | Definition |
|---|---|---|
| temperature_dev | σ | (temperature − machine baseline mean) / baseline std |
| vibration_dev | σ | same for vibration (mm/s) |
| pressure_dev | σ | same for pressure (bar); signed |
| load_pct | % | machine load 0–100 |
| equipment_age_years | years | now − install date |
| maintenance_delay_days | days | days the oldest open maintenance task is overdue (0 if none) |
| previous_incidents | count | incidents on this machine in the last 90 days |
| shift_hours | hours | hours into the current shift (overtime can exceed 8) |
| production_intensity | 0–1 | production load proxy |
| weather_severity | 0–1 | environmental stress proxy |
| inspection_status | 0/1/2 | latest inspection: pass / conditional / fail |
| temperature_trend, vibration_trend | σ | current deviation minus mean deviation 30 min–3 h ago |
Target (training only): `accident_next_6h` ∈ {0,1}.

## Sample dataset
`data/sample/synthetic_risk_sample.csv` — 3 synthetic machines × 14 days, 30-minute steps (2,016 rows). Columns = the raw sensors (`temperature`, `vibration`, `pressure`, `load_pct`), the model features above, `load_dev`, `degradation_level` (latent ground truth, not available in production), `machine_id`, `machine_type`, `timestamp`, and the target. Generate more with:
`cd backend && python -m app.ml.training.data_gen --machines 24 --days 90 --out ../data/processed/synthetic_risk.csv`

## Machine baselines
`machines.baseline` JSON: `{parameter: {mean, std}}` for temperature (°C), vibration (mm/s), pressure (bar), load_pct (%). Defaults come from the machine type (`ml/common.py::MACHINE_TYPES`); replace with statistics from your own healthy operation periods.
