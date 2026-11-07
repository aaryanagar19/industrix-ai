"""Reproducible SYNTHETIC industrial dataset generator.

IMPORTANT: everything produced here is synthetic. Labels come from a documented latent hazard function
(see `HAZARD_COEFFS`) plus noise; models trained on this data demonstrate the pipeline, NOT real-world
predictive performance. Replace with real incident-labelled plant data before any operational use.

Usage:  python -m app.ml.training.data_gen --machines 24 --days 90 --out ../data/sample/synthetic_risk.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.common import MACHINE_TYPES, baseline_for

HAZARD_COEFFS = dict(
    bias=-7.7, temp=0.75, vib=0.70, press=0.35, load=0.06, age=0.18, delay=0.015, prev=0.25,
    shift=0.12, prod=0.5, weather=0.6, insp=0.7, interact=0.25,
)
LABEL_HORIZON_STEPS = 12  # label = serious event within the next 12 steps (6h at 30-min spacing)


def _ar1(n, phi, sigma, rng):
    x = np.zeros(n)
    e = rng.normal(0, sigma, n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def _episodes(n, steps_per_day, rate_per_day, dur_range_h, rng, steps_per_hour):
    """Return degradation level in [0,1]: ramp-up during an episode, abrupt drop at the end (repair)."""
    level = np.zeros(n)
    t = 0
    while t < n:
        gap = rng.exponential(steps_per_day / rate_per_day)
        t += int(gap)
        if t >= n:
            break
        dur = int(rng.uniform(*dur_range_h) * steps_per_hour)
        end = min(t + dur, n)
        level[t:end] = np.linspace(0.05, 1.0, end - t) ** 0.8
        t = end
    return level


def generate_machine_series(machine_type, n_steps, freq_minutes, start, rng, age_years=None, baseline=None):
    spd = int(24 * 60 / freq_minutes)
    sph = 60 / freq_minutes
    base = baseline or baseline_for(machine_type, 0.03, rng)
    ts = pd.date_range(start, periods=n_steps, freq=f"{freq_minutes}min")
    hour = ts.hour.values + ts.minute.values / 60

    deg = _episodes(n_steps, spd, 1 / 12, (8, 40), rng, sph)
    overload = _episodes(n_steps, spd, 1 / 5, (2, 6), rng, sph)
    overload = (overload > 0).astype(float)

    daily = np.sin(2 * np.pi * (hour - 8) / 24)
    load_mean, load_std = base["load_pct"]["mean"], base["load_pct"]["std"]
    load_true = np.clip(load_mean + 0.9 * load_std * daily + _ar1(n_steps, 0.9, load_std * 0.35, rng) + overload * rng.uniform(22, 32), 5, 100)
    load_z = (load_true - load_mean) / load_std

    def sensor(key, deg_gain, load_gain):
        m, s = base[key]["mean"], base[key]["std"]
        return m + s * (_ar1(n_steps, 0.85, 0.45, rng) + load_gain * load_z + deg_gain * deg)

    temp_true = sensor("temperature", 3.8, 0.35)
    vib_true = sensor("vibration", 4.2, 0.2)
    press_sd = base["pressure"]["std"]
    press_true = sensor("pressure", 0.0, 0.1) + press_sd * deg * rng.choice([-1, 1]) * 2.5 + press_sd * deg * 1.5 * rng.normal(size=n_steps)

    shift_start = np.array([6, 14, 22])
    since = (hour[:, None] - shift_start[None, :]) % 24
    shift_hours = since.min(axis=1)
    ot_day = _episodes(n_steps, spd, 1 / 6, (2, 4), rng, sph) > 0
    shift_hours = shift_hours + ot_day * rng.uniform(2, 4)
    weather = np.clip(0.3 + _ar1(n_steps, 0.995, 0.03, rng) + 0.15 * np.sin(2 * np.pi * np.arange(n_steps) / (spd * 7)), 0, 1)
    prod = np.clip(load_true / 100 + rng.normal(0, 0.05, n_steps), 0, 1)

    # maintenance sawtooth: nominal 30-day interval, random slippage
    delay = np.zeros(n_steps)
    last = -rng.integers(0, 20 * spd)
    interval = 30 * spd
    slip = rng.integers(0, 10 * spd)
    for i in range(n_steps):
        if i - last > interval + slip:
            if rng.random() < 0.02:  # eventually serviced
                last = i
                slip = rng.integers(0, 10 * spd)
        delay[i] = max(0.0, (i - last - interval) / spd)
    insp = np.zeros(n_steps)
    for i in range(0, n_steps, 14 * spd):
        p_fail = min(0.05 + 0.4 * deg[i:i + 14 * spd].mean() + 0.01 * delay[i], 0.9)
        r = rng.random()
        insp[i:i + 14 * spd] = 2 if r < p_fail * 0.4 else (1 if r < p_fail else 0)
    age = age_years if age_years is not None else rng.uniform(1, 18)

    return pd.DataFrame({
        "timestamp": ts, "temperature_true": temp_true, "vibration_true": vib_true,
        "pressure_true": press_true, "load_true": load_true, "deg_level": deg,
        "shift_hours": shift_hours, "production_intensity": prod, "weather_severity": weather,
        "maintenance_delay_days": delay, "inspection_status": insp, "equipment_age_years": age,
    }), base


def _hazard_logit(df, base, prev):
    c = HAZARD_COEFFS
    tz = (df.temperature_true - base["temperature"]["mean"]) / base["temperature"]["std"]
    vz = (df.vibration_true - base["vibration"]["mean"]) / base["vibration"]["std"]
    pz = (df.pressure_true - base["pressure"]["mean"]) / base["pressure"]["std"]
    relu = lambda x: np.maximum(x, 0)
    return (c["bias"] + c["temp"] * relu(tz - 1) + c["vib"] * relu(vz - 1) + c["press"] * relu(pz.abs() - 1.5)
            + c["load"] * relu(df.load_true - 80) + c["age"] * df.equipment_age_years / 5 + c["delay"] * df.maintenance_delay_days
            + c["prev"] * prev + c["shift"] * relu(df.shift_hours - 8) + c["prod"] * (df.production_intensity > 0.9)
            + c["weather"] * df.weather_severity + c["insp"] * df.inspection_status
            + c["interact"] * relu(tz - 1) * relu(vz - 1))


def generate_dataset(n_machines=24, days=90, freq_minutes=30, seed=42, start="2025-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    types = list(MACHINE_TYPES)
    n_steps = int(days * 24 * 60 / freq_minutes)
    frames = []
    for m in range(n_machines):
        mtype = types[m % len(types)]
        df, base = generate_machine_series(mtype, n_steps, freq_minutes, start, rng)
        # previous incidents (90d) – rises after degradation episodes
        spd = int(24 * 60 / freq_minutes)
        prev = pd.Series(df.deg_level.rolling(spd * 7, min_periods=1).mean() * 3 + rng.poisson(0.3, n_steps) * 0.1).rolling(spd, min_periods=1).mean().round().clip(0, 6)
        logit = _hazard_logit(df, base, prev)
        hazard = 1 / (1 + np.exp(-(logit + rng.normal(0, 0.5, n_steps))))
        events = rng.random(n_steps) < hazard
        ev = pd.Series(events.astype(int))
        fut = ev[::-1].rolling(LABEL_HORIZON_STEPS, min_periods=1).max()[::-1].shift(-1).fillna(0)  # strictly future
        noise = lambda k: rng.normal(0, 0.12 * base[k]["std"], n_steps)
        out = pd.DataFrame({
            "machine_id": f"SYN-{m + 1:02d}", "machine_type": mtype, "timestamp": df.timestamp,
            "temperature": df.temperature_true + noise("temperature"), "vibration": df.vibration_true + noise("vibration"),
            "pressure": df.pressure_true + noise("pressure"), "load_pct": np.clip(df.load_true + noise("load_pct"), 0, 100),
            "equipment_age_years": df.equipment_age_years, "maintenance_delay_days": df.maintenance_delay_days.round(2),
            "previous_incidents": prev.values, "shift_hours": df.shift_hours.round(2),
            "production_intensity": df.production_intensity.round(3), "weather_severity": df.weather_severity.round(3),
            "inspection_status": df.inspection_status, "degradation_level": df.deg_level.values,
        })
        out["temperature_dev"] = (out.temperature - base["temperature"]["mean"]) / base["temperature"]["std"]
        out["vibration_dev"] = (out.vibration - base["vibration"]["mean"]) / base["vibration"]["std"]
        out["pressure_dev"] = (out.pressure - base["pressure"]["mean"]) / base["pressure"]["std"]
        out["load_dev"] = (out.load_pct - base["load_pct"]["mean"]) / base["load_pct"]["std"]
        trend_n = 6  # previous 6 steps, excluding the current one
        for k, col in (("temperature", "temperature_trend"), ("vibration", "vibration_trend")):
            prior = out[f"{k}_dev"].shift(1).rolling(trend_n, min_periods=3).mean()
            out[col] = out[f"{k}_dev"] - prior
        out["accident_next_6h"] = fut.values.astype(int)
        # inject ~0.5% missing sensor values to exercise missing-data handling
        miss = rng.random(n_steps) < 0.005
        for c in ("temperature_dev", "vibration_dev", "pressure_dev"):
            out.loc[miss & (rng.random(n_steps) < 0.5), c] = np.nan
        out["baseline_json"] = str(base)
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--machines", type=int, default=24)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--freq", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="../data/sample/synthetic_risk.csv")
    a = ap.parse_args()
    d = generate_dataset(a.machines, a.days, a.freq, a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out, index=False)
    print(f"wrote {len(d):,} rows to {a.out}; positive rate = {d.accident_next_6h.mean():.3%}")
