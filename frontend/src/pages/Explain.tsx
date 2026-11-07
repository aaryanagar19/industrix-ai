import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bar, BarChart, XAxis as RX, YAxis as RY } from "recharts";
import { Async, Badge, Card, CardHeader, Disclaimer, Empty, PageHeader, RiskBadge, Table, Tabs } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { ExplanationView } from "../components/Explanation";
import { ChartBox, axis, grid, tip } from "../components/Charts";
import { useGet } from "../hooks/useApi";
import { api } from "../services/api";
import { C, FEATURE_LABEL, pct, when } from "../utils/format";

function ShapImage() {
  const [src, setSrc] = useState<string>(""); const [err, setErr] = useState(false);
  useEffect(() => { let u = ""; api.blob("/api/ai/shap-summary.png").then((b) => { u = URL.createObjectURL(b); setSrc(u); }).catch(() => setErr(true)); return () => { if (u) URL.revokeObjectURL(u); }; }, []);
  return err ? <Empty text="SHAP summary plot not generated" hint="Run model training." /> : src ? <img src={src} alt="SHAP summary plot" className="w-full rounded-lg bg-white" /> : <div className="skeleton h-72" />;
}

function Metrics({ perf }: { perf: any }) {
  const r = perf.risk;
  if (!r?.models) return <Empty text="No model metrics" />;
  return (
    <div className="space-y-4">
      <Disclaimer><b>Synthetic data.</b> {perf.data_origin_warning}</Disclaimer>
      <div className="grid gap-4 lg:grid-cols-2">
        {Object.entries(r.models).map(([name, m]: any) => (
          <Card key={name}><CardHeader title={name === "xgboost" ? "XGBoost (primary)" : "Random Forest (baseline)"} sub={`ROC-AUC ${m.roc_auc} · PR-AUC ${m.pr_auc} · Brier ${m.brier_calibrated} (uncalibrated ${m.brier_uncalibrated})`} />
            <Table><thead><tr><th className="th">Level ≥</th><th className="th">Thr.</th><th className="th">Accuracy</th><th className="th">Precision</th><th className="th">Recall</th><th className="th">F1</th><th className="th">FNR</th></tr></thead><tbody>
              {Object.entries(m.at_thresholds).map(([lvl, v]: any) => <tr key={lvl} className="border-t border-line/60"><td className="td capitalize">{lvl}</td><td className="td tabular-nums">{v.threshold}</td><td className="td tabular-nums">{v.accuracy}</td><td className="td tabular-nums">{v.precision}</td><td className="td tabular-nums">{v.recall}</td><td className="td tabular-nums">{v.f1}</td><td className="td tabular-nums">{v.false_negative_rate}</td></tr>)}</tbody></Table>
            <div className="grid grid-cols-3 gap-2 p-3 text-xs">{Object.entries(m.at_thresholds).map(([lvl, v]: any) => <div key={lvl} className="rounded-lg bg-surface2 p-2"><b className="capitalize">{lvl}</b><div className="mt-1 text-muted">TP {v.confusion_matrix.tp} · FP {v.confusion_matrix.fp}<br />FN {v.confusion_matrix.fn} · TN {v.confusion_matrix.tn}</div></div>)}</div></Card>
        ))}
      </div>
      <Card className="p-4 text-sm"><p className="label">How thresholds are selected</p><p>{perf.threshold_method}</p><p className="mt-2 text-muted">Splits: {r.split}. Train/val/test rows: {r.rows.train.toLocaleString()} / {r.rows.validation.toLocaleString()} / {r.rows.test.toLocaleString()}. Positive rate (test): {pct(r.positive_rate.test)}. Active thresholds: moderate {perf.active_thresholds?.moderate}, high {perf.active_thresholds?.high}, critical {perf.active_thresholds?.critical}.</p></Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4 text-sm"><p className="label">Anomaly detector (synthetic evaluation)</p><ul className="space-y-1"><li>False-alarm rate on healthy periods: <b>{pct(perf.anomaly.flag_rate_healthy_periods_heldout)}</b></li><li>Flag rate during severe degradation: <b>{pct(perf.anomaly.flag_rate_during_severe_degradation_heldout)}</b></li>{Object.entries(perf.anomaly.detection_rate_on_injected_anomalies || {}).map(([k, v]: any) => <li key={k} className="text-muted">{k.replace(/_/g, " ")}: {pct(v, 0)}</li>)}</ul></Card>
        <Card className="p-4 text-sm"><p className="label">NLP classifier</p><p>Held-out-template accuracy: classifier only <b>{perf.nlp.heldout_template_accuracy_classifier_only}</b>, full pipeline with rule fallback <b>{perf.nlp.heldout_template_accuracy_full_pipeline}</b>.</p><p className="mt-2 text-xs text-muted">{perf.nlp.note}</p></Card>
      </div>
    </div>
  );
}

export default function Explain() {
  const [sp] = useSearchParams(); const [tab, setTab] = useState(sp.get("prediction") ? "single" : "global"); const [machine, setMachine] = useState(""); const [pid, setPid] = useState(sp.get("prediction") || "");
  const perf = useGet<any>("/api/ai/model-performance");
  const preds = useGet<any>("/api/ai/predictions", { machine_id: machine || undefined, page_size: 15 });
  const ex = useGet<any>(`/api/ai/explanations/${pid}`, undefined, { enabled: !!pid });
  return (
    <>
      <PageHeader title="Explainable AI" sub="SHAP shows which inputs the accident model relied on. It describes model behaviour and statistical association — not proof of physical causation." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "global", label: "Global importance" }, { id: "single", label: "Single prediction" }, { id: "perf", label: "Model performance" }]} />
      {tab === "global" && <Async q={perf}>{(d) => (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card><CardHeader title="Feature importance ranking" sub="Mean |SHAP| on held-out test sample (log-odds)" /><div className="p-3"><ChartBox h={360}><BarChart data={(d.risk.shap_global || []).map((x: any) => ({ name: FEATURE_LABEL[x.feature] || x.feature, v: x.mean_abs_shap }))} layout="vertical" margin={{ left: 20 }}>{grid}<RX type="number" {...axis} /><RY type="category" dataKey="name" width={200} {...axis} />{tip}<Bar dataKey="v" name="Mean |SHAP|" fill={C.accent} radius={[0, 6, 6, 0]} /></BarChart></ChartBox></div></Card>
          <Card><CardHeader title="SHAP summary plot" sub="Each dot is a sample; colour = feature value; x = effect on risk" /><div className="p-3"><ShapImage /></div></Card>
          <div className="lg:col-span-2"><Disclaimer>{d.risk.shap_note}</Disclaimer></div>
        </div>)}</Async>}
      {tab === "single" && (
        <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
          <Card><div className="border-b border-line p-3"><MachinePicker allowAll value={machine} onChange={setMachine} className="w-full" /></div>
            <div className="max-h-[560px] divide-y divide-line/60 overflow-y-auto">{preds.data?.items?.length ? preds.data.items.map((p: any) => <button key={p.id} onClick={() => setPid(String(p.id))} className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-surface2 ${pid === String(p.id) ? "bg-accent/10" : ""}`}><span><b>{p.machine_code}</b><br /><span className="text-xs text-muted">{when(p.timestamp)}</span></span><span className="flex items-center gap-2 tabular-nums">{pct(p.probability)}<RiskBadge level={p.category} /></span></button>) : <Empty text="No predictions" />}</div></Card>
          <Card>{pid ? <Async q={ex}>{(d) => (<><CardHeader title={`${d.prediction.machine_code} — ${pct(d.prediction.probability)} (${d.prediction.category})`} sub={`${when(d.prediction.timestamp)} · ${d.prediction.model_version}`} right={<Badge color={d.prediction.data_quality?.status === "ok" ? "ok" : "warn"}>Data: {d.prediction.data_quality?.status}</Badge>} /><div className="p-4"><ExplanationView e={d.explanation} baseline={d.baseline_comparison} /></div></>)}</Async> : <Empty text="Select a prediction to explain" />}</Card>
        </div>
      )}
      {tab === "perf" && <Async q={perf}>{(d) => <Metrics perf={d} />}</Async>}
    </>
  );
}
