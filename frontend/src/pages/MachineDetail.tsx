import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ReferenceArea, XAxis as RX, YAxis as RY } from "recharts";
import { Async, Button, Card, CardHeader, Confirm, Empty, PageHeader, RiskBadge, Select, SimBanner, StatusBadge, Table, useToast } from "../components/ui";
import { ChartBox, axis, ddhh, grid, hhmm, tip } from "../components/Charts";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { C, PARAMS, ago, num, pct, title, when } from "../utils/format";

export default function MachineDetail() {
  const { id } = useParams(); const nav = useNavigate(); const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient();
  const [hours, setHours] = useState(6); const [del, setDel] = useState(false);
  const q = useGet<any>(`/api/machines/${id}`, undefined, { refetchMs: 15000 });
  const h = useGet<any>(`/api/sensors/${id}/history`, { hours, max_points: 240 }, { refetchMs: 20000 });
  const upd = useMutation({ mutationFn: (status: string) => api.patch(`/api/machines/${id}`, { status }), onSuccess: () => { toast("Status updated", "success"); qc.invalidateQueries({ queryKey: [`/api/machines/${id}`] }); }, onError: (e: any) => toast(e.message, "error") });
  const rm = useMutation({ mutationFn: () => api.del(`/api/machines/${id}`), onSuccess: () => { toast("Machine deleted", "success"); nav("/monitoring"); }, onError: (e: any) => toast(e.message, "error") });
  return (
    <Async q={q}>{(m) => (<>
      <PageHeader title={`${m.code} — ${m.name}`} sub={`${m.department || "Unassigned"} · ${title(m.machine_type)} · ${m.age_years.toFixed(1)} years old · ${num(m.operating_hours, 0)} operating hours`}
        actions={<>
          <Link to={`/prediction?machine=${m.id}`} className="btn-ghost">Predict</Link><Link to={`/forecast?machine=${m.id}`} className="btn-ghost">Forecast</Link>
          {can("plant_manager") && <Select aria-label="Status" value={m.status} onChange={(e) => upd.mutate(e.target.value)} className="w-36">{["running", "idle", "maintenance", "offline"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>}
          {can() && <Button variant="danger" onClick={() => setDel(true)}>Delete</Button>}
        </>} />
      <SimBanner />
      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="p-4"><p className="label">Current risk</p><div className="flex items-center gap-3"><span className="text-3xl font-semibold tabular-nums">{pct(m.risk?.probability)}</span><RiskBadge level={m.risk?.category} /></div><p className="mt-2 text-xs text-muted">{m.risk ? `${ago(m.risk.timestamp)} · ${m.risk.model_version}` : "No prediction yet"}</p><div className="mt-3"><StatusBadge s={m.status} /></div></Card>
        <Card className="p-4"><p className="label">Model context</p><dl className="grid grid-cols-2 gap-y-1 text-sm"><dt className="text-muted">Maintenance overdue</dt><dd>{num(m.context.maintenance_delay_days)} d</dd><dt className="text-muted">Incidents (90 d)</dt><dd>{m.context.previous_incidents}</dd><dt className="text-muted">Inspection</dt><dd>{["Pass", "Conditional", "Fail"][m.context.inspection_status]}</dd><dt className="text-muted">Last inspection</dt><dd>{when(m.last_inspection_at)}</dd></dl></Card>
        <Card className="p-4"><p className="label">Normal baseline (mean ± σ)</p><dl className="grid grid-cols-2 gap-y-1 text-sm">{PARAMS.map((p) => <Fragment key={p.key}><dt className="text-muted">{p.label}</dt><dd className="tabular-nums">{num(m.baseline[p.key]?.mean, 1)} ± {num(m.baseline[p.key]?.std, 2)} {p.unit}</dd></Fragment>)}</dl></Card>
      </div>
      <Card className="mt-4"><CardHeader title="Sensor history" right={<Select aria-label="History range" value={hours} onChange={(e) => setHours(+e.target.value)} className="w-28"><option value={1}>1 h</option><option value={6}>6 h</option><option value={24}>24 h</option><option value={168}>7 d</option></Select>} />
        <div className="grid gap-3 p-3 sm:grid-cols-2">{PARAMS.map((p) => { const b = m.baseline[p.key]; return (
          <div key={p.key}><p className="mb-1 text-xs font-medium">{p.label} ({p.unit})</p>
            <ChartBox h={150}><LineChart data={h.data?.points || []}>{grid}{b && <ReferenceArea y1={b.mean - 2 * b.std} y2={b.mean + 2 * b.std} fill={C.ok} fillOpacity={0.08} />}<RX dataKey="timestamp" tickFormatter={hours > 24 ? ddhh : hhmm} {...axis} minTickGap={40} /><RY domain={["auto", "auto"]} {...axis} width={38} tickFormatter={(v) => Number(v).toFixed(1)} />{tip}<Line dataKey={p.key} stroke={C.accent} dot={false} strokeWidth={1.6} isAnimationActive={false} /></LineChart></ChartBox></div>); })}</div></Card>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Maintenance history" />{m.maintenance_history.length ? <Table><thead><tr><th className="th">Task</th><th className="th">Priority</th><th className="th">Status</th><th className="th">Due</th></tr></thead><tbody>{m.maintenance_history.map((t: any) => <tr key={t.id} className="border-t border-line/60"><td className="td">{t.title}</td><td className="td"><RiskBadge level={t.priority} /></td><td className="td"><StatusBadge s={t.status} /></td><td className="td">{when(t.due_date)}</td></tr>)}</tbody></Table> : <Empty text="No maintenance records" />}</Card>
        <Card><CardHeader title="Recent anomalies" />{m.recent_anomalies.length ? <Table><thead><tr><th className="th">Time</th><th className="th">Parameter</th><th className="th">Observed</th><th className="th">Severity</th></tr></thead><tbody>{m.recent_anomalies.map((a: any) => <tr key={a.id} className="border-t border-line/60"><td className="td">{when(a.timestamp)}</td><td className="td">{title(a.parameter)}</td><td className="td tabular-nums">{num(a.observed_value, 2)} {a.unit}</td><td className="td"><RiskBadge level={a.severity} /></td></tr>)}</tbody></Table> : <Empty text="No anomalies recorded" />}</Card>
        <Card><CardHeader title="Inspections" />{m.inspections.length ? <div className="divide-y divide-line/60">{m.inspections.map((i: any) => <div key={i.id} className="flex items-center justify-between px-4 py-2 text-sm"><span>{when(i.inspected_at)} — {i.notes || "—"}</span><RiskBadge level={i.status === "fail" ? "Critical" : i.status === "conditional" ? "Moderate" : "Low"} /></div>)}</div> : <Empty text="No inspections" />}</Card>
        <Card><CardHeader title="Dependencies" sub="Configured industrial dependency graph" />{m.dependencies.length ? <div className="divide-y divide-line/60">{m.dependencies.map((d: any, i: number) => <div key={i} className="px-4 py-2 text-sm"><b>{d.source}</b> → <b>{d.target}</b> <span className="text-muted">({d.relation}, weight {d.weight})</span></div>)}</div> : <Empty text="No dependencies configured" />}</Card>
      </div>
      <Confirm open={del} onClose={() => setDel(false)} danger title="Delete machine?" message={`This permanently deletes ${m.code} and all of its readings, predictions and anomalies.`} confirmLabel="Delete" onConfirm={() => rm.mutate()} />
    </>)}</Async>
  );
}
