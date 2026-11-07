"""Standalone simulator that POSTS readings to a running backend over HTTP (like an edge gateway would).
Usage:  python scripts/simulator_client.py --api http://localhost:8000 --email admin@industrix.dev --password Admin@12345 --interval 5
NOTE: the backend also has a built-in in-process simulator (SIMULATOR_AUTOSTART=true). Disable it to avoid duplicate data."""
import argparse
import math
import time
from datetime import datetime, timezone

import httpx
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000"); ap.add_argument("--email", default="admin@industrix.dev")
    ap.add_argument("--password", default="Admin@12345"); ap.add_argument("--interval", type=float, default=5.0); ap.add_argument("--iterations", type=int, default=0, help="0 = forever")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.api, timeout=30)
    tok = c.post("/api/auth/login", json={"email": a.email, "password": a.password}).raise_for_status().json()["access_token"]
    c.headers["Authorization"] = f"Bearer {tok}"
    machines = [m for m in c.get("/api/machines", params={"page_size": 200}).json()["items"] if m["status"] == "running" and m["baseline"]]
    rng = np.random.default_rng(); state = {m["id"]: np.zeros(4) for m in machines}; n = 0
    while a.iterations == 0 or n < a.iterations:
        hour = datetime.now(timezone.utc).hour
        batch = []
        for m in machines:
            s = state[m["id"]] = 0.85 * state[m["id"]] + rng.normal(0, 0.35, 4)
            b = m["baseline"]; vals = {}
            for i, k in enumerate(("temperature", "vibration", "pressure", "load_pct")):
                vals[k] = round(b[k]["mean"] + b[k]["std"] * (s[i] + (0.9 * math.sin(2 * math.pi * (hour - 8) / 24) if k == "load_pct" else 0)), 3)
            vals["load_pct"] = float(np.clip(vals["load_pct"], 0, 100))
            batch.append({"machine_id": m["id"], **vals, "shift_hours": (hour - 6) % 8, "production_intensity": round(vals["load_pct"] / 100, 3), "weather_severity": 0.3, "data_source": "simulated"})
        r = c.post("/api/sensors/readings", json=batch); r.raise_for_status()
        n += 1; print(f"[{n}] posted {len(batch)} readings")
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
