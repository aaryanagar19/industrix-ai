# Completion Checklist

Legend: ✅ implemented **and** exercised by automated tests or the browser E2E run · 🟡 implemented, only partially verified · ❌ not done

## Platform
| Item | Status | Evidence |
|---|---|---|
| React/TS/Vite frontend starts & builds | ✅ | `npm run build`, Playwright |
| FastAPI backend, Swagger, all 27 required endpoints | ✅ | OpenAPI check, 45 pytest |
| JWT auth, bcrypt, RBAC (5 roles), protected routes | ✅ | pytest + E2E role test |
| SQLite dev DB, Alembic migration | ✅ | `alembic upgrade head` / `check` |
| PostgreSQL | 🟡 | migration SQL generated for the PG dialect; no live server run |
| Redis | ❌ | not integrated |
| Simulator + WebSocket live updates, pause/speed/inject | ✅ | E2E (cards change; injection → anomaly → notification) |
| Distinguishes simulated vs hardware data | ✅ | banners, `data_source`, API status |
| A Executive dashboard (filters, live feed, real API data) | ✅ | pytest + E2E |
| B Live monitoring | ✅ | E2E |
| C XGBoost/RF prediction, calibration, thresholds documented | ✅ | pytest, ML_RESULTS |
| D LSTM forecasting + sufficiency warning | ✅ | pytest (insufficient case), screenshots |
| E Isolation-Forest anomalies (hybrid) | ✅ | pytest, E2E |
| F SHAP explanations | ✅ | pytest, UI |
| G NLP (upload/text, report PDF) | ✅ | pytest (upload validation, analysis) |
| H Risk propagation + map | ✅ | pytest, E2E render |
| I Maintenance (create/assign/complete, recs, effectiveness) | ✅ | pytest |
| J Emergency (incident, checklist, timeline, PDF) | ✅ | pytest + E2E |
| K Digital twin (SVG) | ✅ | E2E render + screenshot |
| L Reports CSV/PDF ×8 types | ✅ | pytest (16 combos) + E2E download |
| 18 required pages | ✅ | E2E visits every page with no console errors |
| Dark/light, responsive, toasts, confirms, skeletons, empty/error states | ✅ | E2E (theme, 390 px no overflow) |
| Backend tests | ✅ | 45 pass |
| Frontend tests (Vitest/RTL) | ✅ | 13 pass |
| Browser E2E (Playwright) | ✅ | 10 pass |
| Dockerfiles / compose / GitHub Actions | 🟡 | written, not executed |
| Cloud deployment | ❌ | not performed |
| Screenshots of the working app | ✅ | `docs/screenshots/` (real) |
