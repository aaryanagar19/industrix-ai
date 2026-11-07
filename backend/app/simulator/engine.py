"""Industrial sensor SIMULATOR. All readings it produces are tagged data_source='simulated'.
No physical hardware is connected; this exists for demonstration and testing."""
from __future__ import annotations

import asyncio
import math
import time
from datetime import datetime

import numpy as np

from app.core.config import get_settings
from app.core.db import SessionLocal, utcnow
from app.core.ws import manager
from app.models import Machine, MachineDependency
from app.services.ingest import ingest_reading

INJECTIONS = {
    "temperature_spike": {"temperature": 4.5},
    "vibration_surge": {"vibration": 5.0},
    "pressure_instability": {"pressure": 4.0},
    "overload": {"load_pct": 4.5},
    "combined_fault": {"temperature": 3.5, "vibration": 4.0, "pressure": 2.5},
}


class Simulator:
    def __init__(self):
        self.running = True
        self.speed = 1.0
        self.interval = get_settings().simulator_interval_seconds
        self.state: dict[int, dict[str, float]] = {}
        self.injections: dict[int, dict] = {}
        self.weather = 0.3
        self.rng = np.random.default_rng()
        self.task: asyncio.Task | None = None
        self.ticks = 0
        self.last_tick: float | None = None

    # -- control -------------------------------------------------------------------------------------------
    def status(self) -> dict:
        now = time.time()
        return {"mode": "simulated", "hardware_connected": False,
                "notice": "Readings are produced by the built-in simulator; no physical industrial hardware is connected.",
                "running": self.running, "speed": self.speed, "interval_seconds": self.interval, "ticks": self.ticks,
                "last_tick": datetime.utcfromtimestamp(self.last_tick).isoformat() + "Z" if self.last_tick else None,
                "active_injections": [{"machine_id": k, "kind": v["kind"], "remaining_s": max(int(v["until"] - now), 0), "cascade": v["cascade"]} for k, v in self.injections.items() if v["until"] > now]}

    def inject(self, machine_id: int, kind: str, duration_s: int = 60, cascade: bool = False):
        if kind not in INJECTIONS:
            raise ValueError(f"unknown kind '{kind}'")
        now = time.time()
        self.injections[machine_id] = {"kind": kind, "start": now, "until": now + duration_s, "cascade": cascade}

    def clear(self, machine_id: int | None = None):
        self.injections.pop(machine_id, None) if machine_id else self.injections.clear()

    # -- generation ----------------------------------------------------------------------------------------
    def _offset(self, mid: int, key: str, now: float, downstream: dict[int, list[tuple[int, float]]]) -> float:
        total = 0.0
        for src, inj in list(self.injections.items()):
            if inj["until"] + 15 < now:
                self.injections.pop(src, None); continue
            elapsed = now - inj["start"]
            ramp = min(1.0, elapsed / 15) if now <= inj["until"] else max(0.0, 1 - (now - inj["until"]) / 15)
            if src == mid:
                eff = INJECTIONS[inj["kind"]].get(key, 0.0)
                if inj["kind"] == "pressure_instability" and key == "pressure":
                    eff *= math.sin(elapsed * 1.7)
                total += eff * ramp
            elif inj["cascade"] and elapsed > 20:
                w = dict(downstream.get(src, [])).get(mid, 0.0)
                if w and key in ("temperature", "vibration"):
                    total += 0.45 * w * 4.0 * ramp
        return total

    def tick_sync(self) -> list[dict]:
        db = SessionLocal()
        events: list[dict] = []
        try:
            machines = db.query(Machine).filter(Machine.status == "running").all()
            deps = db.query(MachineDependency).all()
            downstream: dict[int, list] = {}
            for d in deps:
                downstream.setdefault(d.source_id, []).append((d.target_id, d.weight))
            now_dt, now = utcnow(), time.time()
            hour = now_dt.hour + now_dt.minute / 60
            self.weather = float(np.clip(self.weather + self.rng.normal(0, 0.01), 0.05, 0.95))
            shift = min((hour - 6) % 8, 12)
            daily = math.sin(2 * math.pi * (hour - 8) / 24)
            for m in machines:
                if not m.baseline:
                    continue
                st = self.state.setdefault(m.id, {k: 0.0 for k in ("temperature", "vibration", "pressure", "load_pct")})
                vals = {}
                for k in st:
                    st[k] = 0.85 * st[k] + self.rng.normal(0, 0.35)
                    z = st[k] + (0.9 * daily if k == "load_pct" else 0.3 * daily * 0.0) + self._offset(m.id, k, now, downstream)
                    b = m.baseline[k]
                    vals[k] = b["mean"] + b["std"] * z
                vals["load_pct"] = float(np.clip(vals["load_pct"], 0, 100))
                vals["pressure"] = max(vals["pressure"], 0.0)
                payload = {**{k: round(float(v), 3) for k, v in vals.items()}, "shift_hours": round(shift, 2), "production_intensity": round(float(vals["load_pct"] / 100), 3),
                           "weather_severity": round(self.weather, 3), "timestamp": now_dt}
                events.append(ingest_reading(db, m, payload, "simulated"))
            self.ticks += 1
            self.last_tick = now
        finally:
            db.close()
        return events

    async def run(self):
        while True:
            try:
                if self.running:
                    events = await asyncio.to_thread(self.tick_sync)
                    for ev in events:
                        await manager.broadcast({"type": "reading", "data": ev["reading"]})
                        if ev["prediction"]:
                            await manager.broadcast({"type": "prediction", "data": ev["prediction"]})
                        if ev["anomaly"]:
                            await manager.broadcast({"type": "anomaly", "data": ev["anomaly"]})
                        for n in ev["notifications"]:
                            await manager.broadcast({"type": "notification", "data": n})
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep simulator alive
                import logging
                logging.getLogger("industrix.sim").exception("simulator tick failed: %s", e)
            await asyncio.sleep(max(self.interval / max(self.speed, 0.1), 0.2))


simulator = Simulator()
