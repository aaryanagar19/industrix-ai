"""Train every model:  python -m app.ml.training.train_all [--fast]"""
import argparse
import json
import time

from app.ml.anomaly_detection.train_anomaly import train_anomaly
from app.ml.forecasting.lstm import train_forecaster
from app.ml.nlp.pipeline import train_nlp
from app.ml.training.data_gen import generate_dataset
from app.ml.training.train_risk import train_risk


def main(fast=False, seed=42, only=None):
    t0 = time.time()
    df = generate_dataset(n_machines=12 if fast else 24, days=45 if fast else 90, seed=seed)
    print(f"dataset: {len(df):,} rows, positive rate {df.accident_next_6h.mean():.2%}")
    steps = {"risk": lambda: train_risk(df, seed, fast), "anomaly": lambda: train_anomaly(df, seed, fast),
             "forecast": lambda: train_forecaster(df, seed, fast), "nlp": lambda: train_nlp(seed)}
    for name, fn in steps.items():
        if only and name not in only:
            continue
        t = time.time(); fn(); print(f"[{name}] done in {time.time() - t:.0f}s")
    print(f"all done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    main(a.fast, a.seed, a.only)
