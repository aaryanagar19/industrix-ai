# ML Results (auto-generated from `models/metrics_*.json`)

> **All results are on SYNTHETIC data** produced by `backend/app/ml/training/data_gen.py`. They demonstrate that the pipeline works and is leakage-free; they are **not** evidence of real-world accident-prediction performance.

## Accident-risk classifiers

- Version: `risk-xgb-202611040919` - trained 2026-11-04T09:19:54.173044Z
- Split: chronological 65/15/20 with 6h purge gap
- Rows train/val/test: 67,104 / 15,264 / 20,736
- Positive rate train/val/test: 5.09% / 4.80% / 4.79%
- Learned thresholds (calibrated probability): {'moderate': 0.0143, 'high': 0.1262, 'critical': 0.1704}

### xgboost

ROC-AUC **0.8695** - PR-AUC **0.5537** - Brier (uncalibrated -> Platt-calibrated) 0.0382 -> 0.0278

| Level | Threshold | Accuracy | Precision | Recall | F1 | False-negative rate | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|---|---|
| moderate | 0.0143 | 0.4095 | 0.0696 | 0.9164 | 0.1294 | 0.0836 | 910 | 12161 | 83 | 7582 |
| high | 0.1262 | 0.9603 | 0.5744 | 0.6566 | 0.6128 | 0.3434 | 652 | 483 | 341 | 19260 |
| critical | 0.1704 | 0.9629 | 0.6069 | 0.6405 | 0.6232 | 0.3595 | 636 | 412 | 357 | 19331 |

### random_forest

ROC-AUC **0.8763** - PR-AUC **0.5403** - Brier (uncalibrated -> Platt-calibrated) 0.0642 -> 0.0285

| Level | Threshold | Accuracy | Precision | Recall | F1 | False-negative rate | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|---|---|
| moderate | 0.0145 | 0.2873 | 0.0607 | 0.9597 | 0.1142 | 0.0403 | 953 | 14738 | 40 | 5005 |
| high | 0.0991 | 0.9601 | 0.5722 | 0.6626 | 0.6141 | 0.3374 | 658 | 492 | 335 | 19251 |
| critical | 0.1338 | 0.9633 | 0.6128 | 0.6344 | 0.6235 | 0.3656 | 630 | 398 | 363 | 19345 |

### SHAP global importance (mean |SHAP|, log-odds)

| Feature | Mean abs SHAP |
|---|---|
| vibration_dev | 0.6052 |
| temperature_dev | 0.5135 |
| inspection_status | 0.1166 |
| weather_severity | 0.0464 |
| equipment_age_years | 0.0462 |
| pressure_dev | 0.0437 |
| load_pct | 0.0308 |
| vibration_trend | 0.021 |
| temperature_trend | 0.0158 |
| production_intensity | 0.0103 |
| maintenance_delay_days | 0.0058 |
| shift_hours | 0.0016 |
| previous_incidents | 0.0 |

## Anomaly detector (Isolation Forest + z-score guard rail)

- Version `anomaly-iforest-202611040918`; trained on: healthy reference period (latent degradation < 0.05)
- Flag rate on healthy held-out periods (false-alarm rate): **1.40%**
- Flag rate during severe degradation: **78.25%**
- Detection of injected deviations:

  - temperature_spike_+5σ: 100.0%
  - vibration_surge_+5σ: 100.0%
  - pressure_instability_±5σ: 100.0%
  - load_overload_+4σ: 71.0%
  - combined_mild_+2.5σ_on_all: 56.9%
  - combined_mild_+2σ_temp_vib: 0.0%

> Hybrid detector (Isolation Forest + z-score guard). Flag rate on healthy periods is the false-alarm rate; flag rate during degradation is the detection rate. Detection rates are on synthetically injected deviations, not on real faults.

## LSTM forecaster

- Version `forecast-lstm-202611040918`; window 24 h -> horizon 24 h; samples {'train': 10872, 'validation': 936, 'test': 1368}; epochs run 9
- Test MAE in sigma units (lower is better):

| Model | temperature_dev | vibration_dev | pressure_dev | load_dev |
|---|---|---|---|---|
| lstm | 0.7731 | 0.7833 | 0.7228 | 0.672 |
| baseline_zero | 0.8322 | 0.8308 | 0.745 | 0.8858 |
| persistence_baseline | 1.0614 | 1.0252 | 0.9705 | 1.1589 |

> Metrics are on a chronological held-out segment of SYNTHETIC data, in z-score units. The persistence baseline repeats the last observed value; baseline_zero predicts the machine always sits at its normal baseline.

## NLP classifier

- `nlp-tfidf-lr-202611040918`; classes ['equipment_failure', 'fire_overheat', 'leak_spill', 'electrical', 'near_miss', 'routine_maintenance', 'personal_injury']
- heldout_template_accuracy_classifier_only: 0.5714
- heldout_template_accuracy_full_pipeline: 0.6667

> Trained on a small templated synthetic corpus; accuracy on held-out templates is optimistic vs. real free-text reports. Rule-based fallbacks are used when classifier confidence is low.
