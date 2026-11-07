"""Train the accident-risk classifiers (XGBoost primary, Random Forest baseline).

Methodology (documented in docs/ML_METHODOLOGY.md):
 * chronological split by time (train 65% / validation 15% / test 20%) with a 6h purge gap at each boundary
   so that look-ahead labels cannot leak across splits;
 * median imputation fitted on the training split only;
 * Platt (sigmoid) probability calibration fitted on the validation split;
 * risk-category thresholds chosen on the validation split (see `choose_thresholds`);
 * every reported metric is computed on the untouched test split.
"""
from __future__ import annotations

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix, f1_score,
                             precision_recall_curve, precision_score, recall_score, roc_auc_score, accuracy_score)
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from app.ml.common import RISK_FEATURES, PlattCalibrator, models_dir
from app.ml.training.data_gen import generate_dataset

TARGET = "accident_next_6h"
MODEL_VERSION_PREFIX = "risk-xgb"


def chronological_split(df: pd.DataFrame, gap_hours: int = 6):
    ts = df["timestamp"]
    t1, t2 = ts.quantile(0.65), ts.quantile(0.80)
    gap = pd.Timedelta(hours=gap_hours)
    train = df[ts < t1 - gap]
    val = df[(ts >= t1) & (ts < t2 - gap)]
    test = df[ts >= t2]
    return train, val, test


def metrics_at(y, p, thr):
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "threshold": round(float(thr), 4), "accuracy": round(accuracy_score(y, pred), 4),
        "precision": round(precision_score(y, pred, zero_division=0), 4), "recall": round(recall_score(y, pred), 4),
        "f1": round(f1_score(y, pred), 4), "false_negative_rate": round(fn / max(fn + tp, 1), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def choose_thresholds(y_val, p_val) -> dict:
    """Moderate = highest threshold still catching >=90% of validation positives (safety-first recall target).
    High = threshold maximising F2 (recall weighted 4x precision).  Critical = lowest threshold with precision>=0.50.
    Ordering is enforced with minimum gaps.  Values can be overridden in Settings (DB) or env vars."""
    prec, rec, thr = precision_recall_curve(y_val, p_val)
    prec, rec = prec[:-1], rec[:-1]
    ok = np.where(rec >= 0.90)[0]
    moderate = float(thr[ok].max()) if len(ok) else float(np.quantile(p_val, 0.7))
    f2 = (5 * prec * rec) / np.maximum(4 * prec + rec, 1e-9)
    high = float(thr[int(np.argmax(f2))])
    okp = np.where(prec >= 0.50)[0]
    critical = float(thr[okp].min()) if len(okp) else float(np.quantile(p_val, 0.97))
    high = max(high, moderate * 1.25)
    critical = max(critical, high * 1.35)
    return {"moderate": round(moderate, 4), "high": round(min(high, 0.9), 4), "critical": round(min(critical, 0.97), 4)}


def reliability(y, p, bins=10):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1))
    edges = np.unique(edges)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p <= hi)
        if m.sum():
            out.append({"mean_predicted": round(float(p[m].mean()), 4), "observed_rate": round(float(y[m].mean()), 4), "n": int(m.sum())})
    return out


def train_risk(df: pd.DataFrame | None = None, seed: int = 42, fast: bool = False, make_plots: bool = True) -> dict:
    out_dir = models_dir()
    if df is None:
        df = generate_dataset(n_machines=12 if fast else 24, days=45 if fast else 90, seed=seed)
    train, val, test = chronological_split(df)
    Xtr, ytr = train[RISK_FEATURES], train[TARGET].values
    Xva, yva = val[RISK_FEATURES], val[TARGET].values
    Xte, yte = test[RISK_FEATURES], test[TARGET].values

    imp = SimpleImputer(strategy="median").fit(Xtr)
    Atr, Ava, Ate = (imp.transform(x) for x in (Xtr, Xva, Xte))

    spw = float((ytr == 0).sum() / max((ytr == 1).sum(), 1))
    xgb = XGBClassifier(n_estimators=250 if fast else 500, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                        min_child_weight=5, reg_lambda=2.0, scale_pos_weight=min(spw, 5.0), eval_metric="aucpr",
                        early_stopping_rounds=30, random_state=seed, n_jobs=1, tree_method="hist")
    xgb.fit(Atr, ytr, eval_set=[(Ava, yva)], verbose=False)
    rf = RandomForestClassifier(n_estimators=80 if fast else 150, max_depth=12, min_samples_leaf=20, class_weight="balanced_subsample",
                                random_state=seed, n_jobs=1).fit(Atr, ytr)

    result = {"trained_at": datetime.utcnow().isoformat() + "Z", "data_origin": "synthetic",
              "rows": {"train": len(train), "validation": len(val), "test": len(test)},
              "positive_rate": {"train": round(float(ytr.mean()), 4), "validation": round(float(yva.mean()), 4), "test": round(float(yte.mean()), 4)},
              "features": RISK_FEATURES, "split": "chronological 65/15/20 with 6h purge gap", "models": {}}
    calibrators, probs_test = {}, {}
    for name, model in (("xgboost", xgb), ("random_forest", rf)):
        raw_va, raw_te = model.predict_proba(Ava)[:, 1], model.predict_proba(Ate)[:, 1]
        cal = PlattCalibrator().fit(raw_va, yva)
        cal_te = cal.predict(raw_te)
        cal_va = cal.predict(raw_va)
        thr = choose_thresholds(yva, cal_va)
        calibrators[name], probs_test[name] = cal, cal_te
        result["models"][name] = {
            "roc_auc": round(roc_auc_score(yte, cal_te), 4), "pr_auc": round(average_precision_score(yte, cal_te), 4),
            "brier_uncalibrated": round(brier_score_loss(yte, raw_te), 4), "brier_calibrated": round(brier_score_loss(yte, cal_te), 4),
            "thresholds": thr,
            "at_thresholds": {k: metrics_at(yte, cal_te, v) for k, v in thr.items()},
            "reliability_curve": reliability(yte, cal_te),
        }
    primary = "xgboost"
    result["thresholds"] = result["models"][primary]["thresholds"]
    result["primary_model"] = primary
    result["version"] = f"{MODEL_VERSION_PREFIX}-{datetime.utcnow():%Y%m%d%H%M}"

    pipe = Pipeline([("imputer", imp), ("clf", xgb)])
    # feature stats for out-of-distribution warnings
    stats = {f: {"p1": float(np.nanpercentile(Xtr[f], 1)), "p99": float(np.nanpercentile(Xtr[f], 99)),
                 "min": float(np.nanmin(Xtr[f])), "max": float(np.nanmax(Xtr[f])), "median": float(np.nanmedian(Xtr[f]))} for f in RISK_FEATURES}

    # SHAP (TreeExplainer on the XGBoost margin = log-odds contributions)
    import shap
    explainer = shap.TreeExplainer(xgb)
    sample = pd.DataFrame(Ate, columns=RISK_FEATURES).sample(min(2000, len(Ate)), random_state=seed)
    sv = explainer.shap_values(sample)
    mean_abs = np.abs(sv).mean(axis=0)
    result["shap_global"] = sorted(({"feature": f, "mean_abs_shap": round(float(v), 4)} for f, v in zip(RISK_FEATURES, mean_abs)), key=lambda d: -d["mean_abs_shap"])
    result["shap_note"] = "SHAP values are in log-odds of the uncalibrated XGBoost margin; they describe model behaviour, not physical causation."
    if make_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        shap.summary_plot(sv, sample, show=False, max_display=13)
        plt.tight_layout()
        plt.savefig(out_dir / "shap_summary.png", dpi=110)
        plt.close()
    bundle = {"pipeline": pipe, "calibrator": calibrators[primary], "features": RISK_FEATURES, "thresholds": result["thresholds"],
              "feature_stats": stats, "version": result["version"], "rf": rf, "rf_calibrator": calibrators["random_forest"], "imputer": imp}
    joblib.dump(bundle, out_dir / "risk_model.joblib", compress=3)
    (out_dir / "metrics_risk.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    r = train_risk()
    print(json.dumps({k: v for k, v in r.items() if k not in ("shap_global",)}, indent=1)[:3500])
