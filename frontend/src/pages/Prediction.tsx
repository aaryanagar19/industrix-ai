import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { Badge, Button, Card, CardHeader, Disclaimer, Empty, Field, Input, PageHeader, Pager, RiskBadge, Select, Table, useToast } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { BaselineTable, ExplanationView } from "../components/Explanation";
import { useGet } from "../hooks/useApi";
import { api } from "../services/api";
import { C, RISK_COLOR, pct, when } from "../utils/format";

const EMPTY = { temperature: "", vibration: "", pressure: "", load_pct: "", shift_hours: "", maintenance_delay_days: "", previous_incidents: "", inspection_status: "" };
const LABELS: Record<string, string> = { temperature: "Temperature (°C)", vibration: "Vibration (mm/s)", pressure: "Pressure (bar)", load_pct: "Load (%)", shift_hours: "Shift hours", maintenance_delay_days: "Maintenance overdue (days)", previous_incidents: "Incidents (90 d)" };

export default function Prediction() {
  const [sp] = useSearchParams(); const toast = useToast(); const qc = useQueryClient();
  const [machine, setMachine] = useState(sp.get("machine") || ""); const [f, setF] = useState<any>(EMPTY); const [res, setRes] = useState<any>(null);
  const [page, setPage] = useState(1); const [cat, setCat] = useState("");
  const hist = useGet<any>("/api/ai/predictions", { page, page_size: 10, machine_id: machine || undefined, category: cat || undefined }, { refetchMs: 15000 });
  const run = useMutation({
    mutationFn: () => { const body: any = { machine_id: +machine, explain: true }; Object.entries(f).forEach(([k, v]) => { if (v !== "") body[k] = k === "inspection_status" ? v : Number(v); }); return api.post("/api/ai/predict", body); },
    onSuccess: (r) => { setRes(r); qc.invalidateQueries({ queryKey: ["/api/ai/predictions"] }); }, onError: (e: any) => toast(e.message, "error"),
  });
  const thr = res?.thresholds;
  return (
    <>
      <PageHeader title="AI Accident Prediction" sub="XGBoost (calibrated) estimate of the probability of a serious event on the selected machine in roughly the next 6 hours. Leave inputs empty to use the latest stored reading; fill any field for a what-if analysis." />
      <Card className="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Machine"><MachinePicker value={machine} onChange={(v) => { setMachine(v); setRes(null); }} className="w-full" /></Field>
          {Object.keys(LABELS).map((k) => <Field key={k} label={LABELS[k]}><Input type="number" step="any" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} placeholder="latest" /></Field>)}
          <Field label="Inspection status"><Select value={f.inspection_status} onChange={(e) => setF({ ...f, inspection_status: e.target.value })}><option value="">latest</option><option value="pass">Pass</option><option value="conditional">Conditional</option><option value="fail">Fail</option></Select></Field>
        </div>
        <div className="mt-4 flex gap-2"><Button onClick={() => run.mutate()} disabled={!machine} loading={run.isPending}><Gauge size={15} />Run prediction</Button><Button variant="ghost" onClick={() => setF(EMPTY)}>Reset inputs</Button></div>
      </Card>

      {res && (
        <Card className="mt-4">
          <CardHeader title={`${res.machine_code} — ${res.machine_name}`} sub={`Predicted ${when(res.timestamp)} · model ${res.model_version}`} right={<Badge color={res.data_quality.status === "ok" ? "ok" : res.data_quality.status === "degraded" ? "warn" : "danger"}>Data quality: {res.data_quality.status}</Badge>} />
          <div className="space-y-5 p-4">
            <div className="flex flex-wrap items-center gap-6">
              <div><p className="label">Accident probability</p><p className="text-4xl font-semibold tabular-nums" style={{ color: RISK_COLOR[res.category] }}>{pct(res.probability)}</p></div>
              <div><p className="label">Risk category</p><RiskBadge level={res.category} /></div>
              <div><p className="label">Response priority</p><p className="text-sm font-medium">{res.priority}</p></div>
              {res.borderline && <Badge color="warn">Near a threshold — uncertain category</Badge>}
            </div>
            {thr && <div><p className="label">Thresholds (calibrated probability)</p><div className="relative h-3 overflow-hidden rounded-full bg-surface2"><div className="absolute inset-y-0 left-0" style={{ width: `${thr.moderate * 100 / 0.4}%`, background: C.ok, opacity: 0.7 }} /><div className="absolute inset-y-0" style={{ left: `${thr.moderate * 100 / 0.4}%`, width: `${(thr.high - thr.moderate) * 100 / 0.4}%`, background: C.warn, opacity: 0.7 }} /><div className="absolute inset-y-0" style={{ left: `${thr.high * 100 / 0.4}%`, width: `${(thr.critical - thr.high) * 100 / 0.4}%`, background: C.orange, opacity: 0.8 }} /><div className="absolute inset-y-0 right-0" style={{ left: `${thr.critical * 100 / 0.4}%`, background: C.danger, opacity: 0.8 }} /><div className="absolute -top-0.5 h-4 w-1 rounded bg-ink" style={{ left: `${Math.min(res.probability * 100 / 0.4, 99)}%` }} /></div><p className="mt-1 text-xs text-muted">Moderate ≥ {pct(thr.moderate)} · High ≥ {pct(thr.high)} · Critical ≥ {pct(thr.critical)} (scale 0–40%)</p></div>}
            {res.data_quality.warnings.map((w: string, i: number) => <Disclaimer key={i}>{w}</Disclaimer>)}
            <ExplanationView e={res.explanation} baseline={res.baseline_comparison} />
            <p className="text-xs text-muted">{res.disclaimer}</p>
          </div>
        </Card>
      )}

      <Card className="mt-4">
        <CardHeader title="Prediction history" sub="Stored model outputs (throttled ~1 per 10 s per machine)" right={<Select aria-label="Category" value={cat} onChange={(e) => { setCat(e.target.value); setPage(1); }} className="w-36"><option value="">All categories</option>{["Low", "Moderate", "High", "Critical"].map((c) => <option key={c}>{c}</option>)}</Select>} />
        {hist.data?.items?.length ? <><Table><thead><tr><th className="th">Time</th><th className="th">Machine</th><th className="th">Probability</th><th className="th">Category</th><th className="th">Data quality</th><th className="th">Model</th><th className="th" /></tr></thead>
          <tbody>{hist.data.items.map((p: any) => <tr key={p.id} className="border-t border-line/60"><td className="td">{when(p.timestamp)}</td><td className="td">{p.machine_code}</td><td className="td tabular-nums">{pct(p.probability)}</td><td className="td"><RiskBadge level={p.category} /></td><td className="td">{p.data_quality?.status}</td><td className="td text-xs text-muted">{p.model_version}</td><td className="td"><Link className="text-accent" to={`/explain?prediction=${p.id}`}>Explain</Link></td></tr>)}</tbody></Table>
          <Pager page={page} total={hist.data.total} size={10} onPage={setPage} /></> : <Empty text="No predictions" />}
      </Card>
    </>
  );
}
