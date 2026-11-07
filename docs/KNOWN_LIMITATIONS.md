# Known Limitations (honest list)

1. **Synthetic data only.** No real incident-labelled industrial dataset was used. All metrics describe the pipeline on synthetic data. Do not use for real safety decisions.
2. **Decision-support prototype**, not a certified safety system. It never controls equipment or notifies emergency services.
3. **Simulated sensors.** No hardware connectors (OPC-UA/MQTT/Modbus). The HTTP ingestion API is the integration point.
4. **Risk categories are recall-first.** Moderate flags many healthy readings (precision ≈ 7 % on the synthetic test set). Tune thresholds in Settings.
5. **Random Forest has slightly higher ROC-AUC than XGBoost** on the synthetic test set (see ML_RESULTS.md); XGBoost is kept as the primary model per the project specification and for SHAP support.
6. **Anomaly detector** misses mild joint deviations (~2σ); a z-score guard covers large single-channel excursions.
7. **LSTM gains over the "always normal" baseline are modest** because most synthetic variance is noise; forecast confidence bands are residual-based, not Bayesian.
8. **NLP** classifier was trained on a small templated corpus; accuracy on real free-text reports will be lower. PDF text extraction requires text-based PDFs (no OCR).
9. **Redis is not integrated.** Rate limiting is in-memory (single instance); there is no job queue. PostgreSQL is supported but only the migration SQL generation was checked here — a live PostgreSQL run is unverified.
10. **Docker, GitHub Actions, Vercel/Render deployment are written but unverified** in the authoring environment.
11. **UI components are hand-written** (Tailwind) rather than shadcn/ui; WebSocket uses the native API rather than Socket.IO.
12. **Demo data gap:** if the server is stopped for a long time after seeding, history has a gap; forecasts flag insufficient contiguous data until enough new readings accrue.
13. Propagation scores, the safety score and the maintenance recommendation score are documented heuristics, not validated models.
14. Prediction rows are throttled and readings are stored every tick — add retention/archival jobs for long-running deployments.
15. No multi-tenant isolation (facility scoping of users is stored but not enforced in queries).
