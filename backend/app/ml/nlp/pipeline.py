"""Practical NLP pipeline: rule-based entity/hazard/issue extraction + TF-IDF/LogReg incident-type classifier.
Works offline. An OpenAI-compatible LLM can optionally add a summary (LLM_BASE_URL / LLM_API_KEY)."""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from datetime import datetime

import joblib
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.pipeline import make_pipeline

from app.core.config import get_settings
from app.ml.common import models_dir

HAZARDS = ["fire", "smoke", "gas leak", "leak", "leaking", "overheat", "overheating", "explosion", "electrical shock", "spark", "sparking",
           "pressure release", "toxic", "chemical spill", "spill", "slip", "fall", "fumes", "burn", "flammable", "short circuit", "noise",
           "hot surface", "unguarded", "entanglement", "falling object", "oil mist"]
ISSUES = ["bearing wear", "bearing", "misalignment", "lubrication", "low oil", "oil leak", "excessive vibration", "vibration", "loose bolt", "loose",
          "corrosion", "crack", "cracked", "seal failure", "worn belt", "belt", "clogged filter", "filter", "calibration drift", "overheating",
          "sensor fault", "valve stuck", "pressure drop", "pressure spike", "coolant", "noise", "wear", "rust", "fault", "alarm", "tripped", "failure"]
URGENT_HIGH = ["immediate", "immediately", "urgent", "asap", "emergency", "critical", "shutdown", "shut down", "evacuate", "stop work", "danger", "unsafe"]
URGENT_MED = ["soon", "this week", "priority", "required", "needs attention", "should be", "recommend", "next shift"]
FOLLOW_VERBS = ["replace", "inspect", "recheck", "re-check", "schedule", "tighten", "lubricate", "monitor", "repair", "calibrate", "clean", "isolate",
                "investigate", "replace", "check", "verify", "service", "escalate", "report"]
MACHINE_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")
MEASURE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(°\s?C|degC|C\b|mm/s|bar|psi|%|rpm|kPa)", re.I)
STOP = set(ENGLISH_STOP_WORDS) | {"machine", "was", "has", "had", "found", "noted", "observed", "also", "today", "during"}

CLASSES = ["equipment_failure", "fire_overheat", "leak_spill", "electrical", "near_miss", "routine_maintenance", "personal_injury"]
_TEMPLATES = {
    "equipment_failure": ["{m} stopped unexpectedly due to {i}; production halted until repair", "Breakdown on {m}: {i} caused a failure of the drive unit",
                          "{m} tripped on fault alarm, {i} suspected, technician called", "Operator reported {m} making grinding noise, {i} found on inspection",
                          "Unplanned downtime for {m} after {i}", "{m} failed under load, probable cause {i}", "{i} led to seizure of {m} spindle", "Equipment fault: {m} shut down, {i} confirmed"],
    "fire_overheat": ["Smoke observed near {m}, temperature reached {t} degC and {i}", "{m} overheating, hot surface and burning smell reported", "Small fire extinguished at {m} after {i}",
                      "Thermal alarm on {m}: temperature {t} C above limit, {i}", "{m} casing too hot to touch, coolant low", "Burning odour from {m}, possible {i}", "Flames seen at {m} wiring, fire extinguisher used", "{m} temperature spike {t} C, smoke from vents"],
    "leak_spill": ["Oil leak found under {m}, floor slippery", "Hydraulic fluid spill near {m} after seal failure", "Gas leak smell reported close to {m}", "Coolant leaking from {m} joint, spill cleaned",
                   "{m} leaking at flange, puddle on floor", "Chemical spill beside {m}, area cordoned", "Steam leak detected on {m} line, pressure dropping", "Fluid dripping from {m}, {i}"],
    "electrical": ["Electrical shock reported while servicing {m}", "Sparking observed in {m} control panel", "Short circuit tripped breaker for {m}", "Exposed wiring found at {m}, danger of shock",
                   "{m} motor burnt winding, electrical fault", "Arc flash near {m} cabinet, short circuit suspected", "Power surge damaged {m} drive", "Loose terminal in {m} panel causing sparking"],
    "near_miss": ["Near miss: tool fell near operator at {m}, no injury", "Near miss at {m}, forklift almost hit worker", "Guard missing on {m}, nearly caught hand, near miss reported",
                  "Close call: pressure release at {m} while operator nearby, nobody hurt", "Near miss, worker almost slipped at {m}", "Unsafe condition near {m}, near miss logged",
                  "No injury but hot part dropped beside {m}", "Almost entangled sleeve in {m} conveyor, near miss"],
    "routine_maintenance": ["Routine lubrication of {m} completed, all readings normal", "Scheduled inspection of {m} done, filter replaced", "Monthly service on {m}: belt checked, bolts tightened",
                            "Preventive maintenance {m} completed, calibration verified", "{m} oil changed per schedule, no issues", "Quarterly check of {m} finished, minor cleaning",
                            "Planned maintenance window used to inspect {m}, wear within limits", "Routine check {m}: sensors calibrated, performance normal"],
    "personal_injury": ["Worker slipped near {m} and sprained ankle", "Operator burned hand on hot surface of {m}", "Employee injured finger while clearing jam on {m}",
                        "Technician fell from ladder at {m}, first aid given", "Worker cut arm on sharp edge of {m}, medical attention required", "Injury report: back strain lifting part at {m}",
                        "Contractor hit by falling object near {m}, taken to clinic", "Operator hand caught in {m} guard gap, treated for bruising"],
}


def synth_corpus(seed=42, n_per_template=6):
    rng = random.Random(seed)
    ms = ["CN-01", "CH-01", "HP-01", "BL-01", "AC-01", "FN-01", "CV-01", "RB-01", "PM-01", "GR-01", "PK-01", "the hydraulic press", "compressor AC-01", "conveyor CV-01"]
    ids = ["bearing wear", "misalignment", "low oil", "worn belt", "seal failure", "clogged filter", "loose bolt", "sensor fault", "excessive vibration"]
    data = []
    for cls, temps in _TEMPLATES.items():
        for ti, t in enumerate(temps):
            for _ in range(n_per_template):
                text = t.format(m=rng.choice(ms), i=rng.choice(ids), t=rng.randint(80, 480))
                data.append((text, cls, ti))
    return data


def train_nlp(seed: int = 42) -> dict:
    data = synth_corpus(seed)
    # split BY TEMPLATE (unseen phrasings in test) to avoid trivial leakage
    train = [(t, c) for t, c, ti in data if ti < 6]
    test = [(t, c) for t, c, ti in data if ti >= 6]
    pipe = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1), LogisticRegression(max_iter=2000, C=5))
    pipe.fit([t for t, _ in train], [c for _, c in train])
    pred = pipe.predict([t for t, _ in test])
    acc = accuracy_score([c for _, c in test], pred)
    meta = {"version": f"nlp-tfidf-lr-{datetime.utcnow():%Y%m%d%H%M}", "trained_at": datetime.utcnow().isoformat() + "Z", "data_origin": "synthetic-templates",
            "classes": CLASSES, "n_train": len(train), "n_test": len(test), "heldout_template_accuracy": round(float(acc), 4),
            "note": "Trained on a small templated synthetic corpus; accuracy on held-out templates is optimistic vs. real free-text reports. "
                    "Rule-based fallbacks are used when classifier confidence is low."}
    joblib.dump({"pipe": pipe, "version": meta["version"]}, models_dir() / "nlp_classifier.joblib")
    full = [analyze_text(t)["incident_type"] for t, _ in test]
    meta["heldout_template_accuracy_classifier_only"] = meta.pop("heldout_template_accuracy")
    meta["heldout_template_accuracy_full_pipeline"] = round(float(accuracy_score([c for _, c in test], full)), 4)
    (models_dir() / "metrics_nlp.json").write_text(json.dumps(meta, indent=2))
    return meta


_RULES = {"fire_overheat": ["fire", "smoke", "overheat", "burning", "flame", "hot surface"], "leak_spill": ["leak", "spill", "dripping", "puddle"],
          "electrical": ["shock", "spark", "short circuit", "electrical", "arc flash", "wiring"], "near_miss": ["near miss", "close call", "almost"],
          "personal_injury": ["injur", "sprain", "burned hand", "first aid", "medical attention", "cut "], "routine_maintenance": ["routine", "scheduled", "preventive", "monthly service", "quarterly"],
          "equipment_failure": ["failure", "failed", "breakdown", "stopped", "tripped", "seiz"]}


def _find_terms(text_l, lexicon):
    found = []
    for term in sorted(set(lexicon), key=len, reverse=True):
        if re.search(rf"\b{re.escape(term)}\b", text_l) and not any(term in f for f in found):
            found.append(term)
    return found


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 8]


def analyze_text(text: str, known_machines: list[dict] | None = None) -> dict:
    text = text.strip()
    tl = text.lower()
    sents = _sentences(text)
    # entities
    codes = sorted(set(MACHINE_RE.findall(text)))
    names = []
    for m in known_machines or []:
        if m["code"] in codes or (m["name"].lower() in tl and m["name"].lower() not in [n.lower() for n in names]):
            names.append(m["name"])
            if m["code"] not in codes:
                codes.append(m["code"])
    measures = [f"{v} {u.replace(' ', '')}" for v, u in MEASURE_RE.findall(text)][:10]
    hazards, issues = _find_terms(tl, HAZARDS), _find_terms(tl, ISSUES)
    # urgency
    high = _find_terms(tl, URGENT_HIGH)
    med = _find_terms(tl, URGENT_MED)
    urgency = "high" if high else ("medium" if med or hazards else "low")
    # follow-up actions: sentences with action verbs
    follow = [s for s in sents if any(re.search(rf"\b{v}\w*\b", s.lower()) for v in FOLLOW_VERBS)][:6]
    # classification with rule fallback
    method, conf, itype = "rules", 0.0, "equipment_failure"
    try:
        bundle = joblib.load(models_dir() / "nlp_classifier.joblib")
        proba = bundle["pipe"].predict_proba([text])[0]
        conf = float(proba.max())
        itype = str(bundle["pipe"].classes_[proba.argmax()])
        method = "tfidf_logreg"
        version = bundle["version"]
    except Exception:
        version = "rules-only"
    if conf < 0.55:
        votes = Counter({c: sum(tl.count(k) for k in ks) for c, ks in _RULES.items()})
        if votes and votes.most_common(1)[0][1] > 0:
            itype, method = votes.most_common(1)[0][0], "rules_fallback"
    if itype == "routine_maintenance" and (hazards or high):
        urgency = "medium" if urgency == "low" else urgency
    # keywords
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]{3,}", tl) if w not in STOP]
    keywords = [w for w, _ in Counter(words).most_common(8)]
    # extractive summary (sentences ranked by hazard/issue/entity hits)
    scored = sorted(sents, key=lambda s: -(sum(t in s.lower() for t in hazards + issues) + 2 * len(MACHINE_RE.findall(s)) + 2 * any(h in s.lower() for h in URGENT_HIGH)))
    summary = " ".join(scored[:2]) if scored else text[:200]
    llm = _llm_summary(text)
    return {"machines": {"codes": codes, "names": names}, "hazards": hazards, "issues": issues, "measurements": measures, "incident_type": itype,
            "classifier_confidence": round(conf, 3), "classification_method": method, "urgency": urgency, "urgency_indicators": high + med,
            "follow_up_actions": follow, "keywords": keywords, "summary": summary, "llm_summary": llm, "model_version": version,
            "disclaimer": "Automated text analysis; verify against the source document before acting."}


def _llm_summary(text: str) -> str | None:
    s = get_settings()
    if not (s.llm_base_url and s.llm_api_key):
        return None
    try:
        import httpx
        r = httpx.post(s.llm_base_url.rstrip("/") + "/chat/completions", timeout=20, headers={"Authorization": f"Bearer {s.llm_api_key}"},
                       json={"model": s.llm_model, "messages": [{"role": "system", "content": "Summarise this industrial maintenance/incident text in 3 sentences. Do not add facts."}, {"role": "user", "content": text[:6000]}]})
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
