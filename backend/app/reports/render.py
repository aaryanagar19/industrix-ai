import csv
import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.db import utcnow

DISCLAIMER = ("INDUSTRIX AI is a decision-support prototype, not a certified safety controller. Predictions are statistical estimates; actions must be confirmed by "
              "authorised safety personnel following approved facility procedures. It never replaces emergency services or official evacuation procedures.")
S = getSampleStyleSheet()
CELL = S["BodyText"].clone("cell", fontSize=7, leading=8.5)


def _tbl(data, widths=None, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9aa7b5")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 7)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0e3a4d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(st))
    return t


def write_csv(path: Path, rep: dict):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([rep["title"]]); w.writerow(["Generated (UTC)", utcnow().isoformat() + "Z"])
        for k, v in rep["summary"]:
            w.writerow([k, v])
        w.writerow([]); w.writerow(rep["columns"]); w.writerows(rep["rows"])


def write_pdf(path: Path, rep: dict, max_rows: int = 400):
    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=rep["title"])
    el = [Paragraph(f"INDUSTRIX AI - {rep['title']}", S["Title"]), Paragraph(f"Generated {utcnow():%Y-%m-%d %H:%M} UTC", S["Normal"]), Spacer(1, 6),
          _tbl([[Paragraph(str(k), CELL), Paragraph(str(v), CELL)] for k, v in rep["summary"]], [60 * mm, 200 * mm], header=False), Spacer(1, 8)]
    if rep["rows"]:
        n = len(rep["cols"] if "cols" in rep else rep["columns"])
        w = (273 * mm) / n
        data = [rep["columns"]] + [[Paragraph(str(c)[:160], CELL) for c in r] for r in rep["rows"][:max_rows]]
        el.append(_tbl(data, [w] * n))
        if len(rep["rows"]) > max_rows:
            el.append(Paragraph(f"Showing first {max_rows} of {len(rep['rows'])} rows. Download CSV for the complete data.", S["Italic"]))
    else:
        el.append(Paragraph("No records in this period.", S["Normal"]))
    el += [Spacer(1, 10), Paragraph(DISCLAIMER, S["Italic"])]
    doc.build(el)


def write_incident_pdf(path: Path, d: dict):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=f"Incident {d['incident']['id']}")
    inc = d["incident"]
    P = lambda t, s="BodyText": Paragraph(t, S[s])
    el = [P(f"Emergency Response Report - Incident #{inc['id']}", "Title"), P(f"Generated {utcnow():%Y-%m-%d %H:%M} UTC"), Spacer(1, 6),
          P("1. Incident summary", "Heading2"), _tbl([[P(k), P(str(v))] for k, v in [("Title", inc["title"]), ("Type", inc["incident_type"]), ("Severity", inc["severity"]), ("Status", inc["status"]),
              ("Occurred", inc["occurred_at"]), ("Location", d["location"]), ("Affected equipment", d["machine_line"]), ("Assigned team", inc["assigned_team"] or "-"), ("Reported by", d["reported_by"]),
              ("Description", inc["description"] or "-")]], [40 * mm, 135 * mm], header=False), Spacer(1, 6),
          P("2. Reported conditions and risk indicators", "Heading2")]
    el.append(_tbl([["Time", "Risk %", "Category"]] + [[p["timestamp"], f"{p['probability']:.1%}", p["category"]] for p in d["predictions"][:15]], [60 * mm, 30 * mm, 40 * mm]) if d["predictions"] else P("No AI prediction history around the incident time."))
    el += [Spacer(1, 4), P("3. Relevant sensor history (+/-2 h, sampled)", "Heading2")]
    el.append(_tbl([["Time", "Temp", "Vib", "Press", "Load %"]] + [[s["timestamp"], s["temperature"], s["vibration"], s["pressure"], s["load_pct"]] for s in d["sensors"][:20]], [55 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm]) if d["sensors"] else P("No sensor history in window."))
    el += [Spacer(1, 4), P("4. Recommended response actions (system templates - require review by authorised safety personnel)", "Heading2")]
    el += [P(f"- {a['action']} [{a['status']}]") for a in d["actions"] if a["category"] in ("recommended", "checklist")] or [P("None.")]
    el += [P("5. Actions recorded by authorised personnel", "Heading2")]
    el += [P(f"- {a['performed_at'] or a['created_at']} - {a['action']} ({a['performed_by'] or 'n/a'}) [{a['status']}]") for a in d["actions"] if a["category"] == "recorded"] or [P("No actions have been recorded yet.")]
    el += [P("6. Resolution", "Heading2"), P(f"Status: {inc['status']}. {inc['resolution'] or 'Not yet resolved.'}"), Spacer(1, 10), P(DISCLAIMER, "Italic")]
    doc.build(el)
