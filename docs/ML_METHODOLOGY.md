# ML Methodology

Concrete numbers live in [ML_RESULTS.md](ML_RESULTS.md) (auto-generated). **Everything below was trained on synthetic data.**

## Synthetic data (`backend/app/ml/training/data_gen.py`)
Per machine type, normal operation is an AR(1) process around a type-specific baseline with a daily load cycle. Random *degradation episodes* ramp temperature, vibration and pressure instability; *overload episodes* push load. Shift hours, weather, maintenance sawtooth (with slippage), inspections and incident counts are generated alongside.
A latent hazard function (`HAZARD_COEFFS`, logit-linear with one interaction, plus Gaussian noise) produces point events; the label is **"a serious event occurs in the next 12 steps (6 h)"**, computed from *strictly future* events. Sensors are observed with measurement noise and ~0.5 % missing values. Fully reproducible via `--seed`.
Consequence: models can at best recover the generating function. Metrics show the pipeline is sound — not how well real accidents can be predicted.

## Risk classifiers
- Features: see `app/ml/common.py::RISK_FEATURES` / [DATA_DICTIONARY.md](DATA_DICTIONARY.md).
- **Chronological split** 65/15/20 by time with a 6 h purge gap so look-ahead labels cannot straddle a boundary (unit-tested).
- Median imputation fitted on train only; XGBoost (early stopping on validation) and Random Forest baseline with class weighting.
- **Platt (sigmoid) calibration** fitted on the validation split. (Isotonic was tried first; its step function produced a degenerate threshold plateau, so it was replaced.)
- **Thresholds** (chosen on validation, calibrated probabilities): *Moderate* = highest threshold still catching ≥ 90 % of validation positives (recall-first, because missed hazards are costly); *High* = F2-optimal (recall weighted 4× precision); *Critical* = lowest threshold with precision ≥ 50 %; ordering/minimum gaps enforced. Overridable by env vars or in Settings (audit-logged).
- Because Moderate is recall-first, it flags a large share of healthy readings. Raise it in Settings if that is too noisy for your use.
- Imbalance handled with `scale_pos_weight` / `class_weight` (SMOTE/imbalanced-learn was not needed and is not used).
- SHAP: `TreeExplainer` on the XGBoost margin (log-odds). Explanations describe model behaviour, **not causation**.

## Anomaly detection
Hybrid: Isolation Forest on the four σ-deviations + max-|σ| (trained on a healthy reference period) **and** a z-score guard (|z| ≥ 3.5). The guard exists because an Isolation Forest cannot score a point beyond the training range worse than the most extreme training point (an 8σ spike scored the same as 5σ in testing). Mild joint deviations (~+2σ on two channels) are *not* reliably detected — see results.

## LSTM forecaster
Input: 24 hourly steps × (4 σ-channels + sin/cos hour-of-day). Output: next 24 h × 4 channels. Chronological per-machine split with purge gaps; evaluated against persistence and "always-at-baseline" references; uncertainty bands = ±1.96 × held-out residual σ per horizon step. Requires ≥ 24 contiguous hours (48 recommended); otherwise the API returns `insufficient`/`limited` instead of a forecast.

## NLP
Rule-based entity/hazard/issue/urgency/follow-up extraction + TF-IDF/LogReg incident-type classifier trained on a small templated corpus (evaluated on held-out *templates*); rule fallback when confidence < 0.55. Optional OpenAI-compatible summary if `LLM_*` env vars are set.
