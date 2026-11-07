"""Industrial Risk Propagation Engine (analytical estimate - not a confirmed physical failure).

local_i      = min(1, P(accident)_i + 0.25 * anomaly_level_i)                    anomaly_level in {0, .4, .7, 1} (last 15 min)
edge_ij      = weight_ij * (0.5 + 0.5 * cooc_ij)                                 cooc_ij = Laplace-smoothed share of j's high-risk hours in which i was also high-risk (7 days)
propagated_i = 1 - (1 - local_i) * PROD_j (1 - edge_ji * r_j)                    r_j = local_j in hop 1, hop-1 result in hop 2 (max 2 hops, no cycle amplification)
"""
from __future__ import annotations

from datetime import timedelta
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.models import AnomalyRecord, Machine, MachineDependency, RiskPrediction
from app.services import risk as risk_svc
from app.services.common import iso

SEV = {"medium": 0.4, "high": 0.7, "critical": 1.0}


def latest_prediction(db: Session, machine_id: int):
    return db.query(RiskPrediction).filter(RiskPrediction.machine_id == machine_id).order_by(RiskPrediction.timestamp.desc()).first()


def cooccurrence(db: Session, thr: dict, days: int = 7) -> tuple[dict, dict]:
    since = utcnow() - timedelta(days=days)
    hours: dict[int, set] = defaultdict(set)
    for mid, ts in db.query(RiskPrediction.machine_id, RiskPrediction.timestamp).filter(RiskPrediction.timestamp >= since, RiskPrediction.probability >= thr["moderate"]):
        hours[mid].add(ts.replace(minute=0, second=0, microsecond=0))
    for mid, ts in db.query(AnomalyRecord.machine_id, AnomalyRecord.timestamp).filter(AnomalyRecord.timestamp >= since):
        hours[mid].add(ts.replace(minute=0, second=0, microsecond=0))
    return hours, {k: len(v) for k, v in hours.items()}


def compute(db: Session, facility_id: int | None = None) -> dict:
    q = db.query(Machine)
    if facility_id:
        q = q.filter(Machine.facility_id == facility_id)
    machines = {m.id: m for m in q.all()}
    thr = risk_svc.thresholds(db)
    deps = [d for d in db.query(MachineDependency).all() if d.source_id in machines and d.target_id in machines]
    hours, _ = cooccurrence(db, thr)
    since = utcnow() - timedelta(minutes=15)
    anom = defaultdict(float)
    for mid, sev in db.query(AnomalyRecord.machine_id, AnomalyRecord.severity).filter(AnomalyRecord.timestamp >= since):
        anom[mid] = max(anom[mid], SEV.get(sev, 0.4))
    local, prob = {}, {}
    for mid in machines:
        p = latest_prediction(db, mid)
        prob[mid] = p.probability if p else 0.0
        local[mid] = min(1.0, prob[mid] + 0.25 * anom[mid])

    edges = []
    for d in deps:
        hj, hi = hours.get(d.target_id, set()), hours.get(d.source_id, set())   # source influences target
        co = (len(hi & hj) + 0) / (len(hi) + 2) if hi else 0.0  # share of the SOURCE's risky hours in which the target was also risky
        edges.append({"source": d.source_id, "target": d.target_id, "weight": d.weight, "relation": d.relation, "cooccurrence": round(co, 3),
                      "strength": round(d.weight * (0.5 + 0.5 * co), 3)})
    r = dict(local)
    for _ in range(2):
        nxt = {}
        for mid in machines:
            keep = 1 - local[mid]
            for e in edges:
                if e["target"] == mid:
                    keep *= 1 - e["strength"] * r[e["source"]]
            nxt[mid] = 1 - keep
        r = nxt
    cat = lambda p: risk_inf_cat(p, thr)
    nodes = []
    for mid, m in machines.items():
        contribs = sorted(({"machine_id": e["source"], "code": machines[e["source"]].code, "contribution": round(e["strength"] * local[e["source"]], 4)}
                           for e in edges if e["target"] == mid and e["strength"] * local[e["source"]] > 0.005), key=lambda c: -c["contribution"])
        nodes.append({"id": mid, "code": m.code, "name": m.name, "type": m.machine_type, "zone": m.zone, "department_id": m.department_id,
                      "department": m.department.name if m.department else None, "x": m.pos_x, "y": m.pos_y, "local_risk": round(local[mid], 4),
                      "model_probability": round(prob[mid], 4), "anomaly_level": anom[mid], "propagated_risk": round(max(r[mid], local[mid]), 4),
                      "added_by_propagation": round(max(r[mid] - local[mid], 0), 4), "category": cat(max(r[mid], local[mid])), "upstream_contributors": contribs[:3]})
    for e in edges:
        e["flow"] = round(e["strength"] * local[e["source"]], 4)
    return {"generated_at": iso(utcnow()), "nodes": nodes, "edges": edges, "thresholds": thr,
            "disclaimer": "Propagated risk is an ANALYTICAL ESTIMATE derived from configured dependencies and historical co-occurrence. It is not a confirmed physical failure."}


def risk_inf_cat(p, thr):
    from app.ml.inference.risk import categorize
    return categorize(p, thr)
