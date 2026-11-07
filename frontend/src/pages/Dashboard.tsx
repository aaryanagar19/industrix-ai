import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, Cell, Legend, Line, LineChart, XAxis as RX, YAxis as RY } from "recharts";
import { Activity, AlertTriangle, Bell, Cpu, Factory, ShieldCheck, Siren, TrendingUp, Wrench, Zap } from "lucide-react";
import { Async, Badge, Card, CardHeader, Disclaimer, Empty, PageHeader, RiskBadge, Select, Skeleton, Stat } from "../components/ui";
import { ChartBox, axis, ddhh, dd, grid, hhmm, tip } from "../components/Charts";
import { useGet, useMachines } from "../hooks/useApi";
import { useLive } from "../contexts/LiveContext";
import { useAuth } from "../contexts/AuthContext";
import { C, RISK_COLOR, ago, pct } from "../utils/format";

const PALETTE = [C.accent, C.orange, C.ok, C.warn, "#a78bfa", "#f472b6", "#60a5fa", "#34d399"];
const LVL: Record<string, string> = { critical: C.danger, warning: C.warn, info: C.accent };

export default function Dashboard() {
  const { user } = useAuth();
  const [hours, setHours] = useState<number>(user?.preferences?.default_hours || 24); const [dept, setDept] = useState(""); const [machine, setMachine] = useState(""); const [group, setGroup] = useState("fleet");
  const machines = useMachines();
  const params = { hours, department_id: dept || undefined, machine_id: machine || undefined };
  const ov = useGet("/api/dashboard/overview", params, { refetchMs: 10000 });
  const tr = useGet("/api/dashboard/risk-trends", { hours, group_by: group, machine_id: machine || undefined }, { refetchMs: 15000 });
  const pr = useGet("/api/ai/predicted-risk", undefined, { refetchMs: 120000 });
  const inc = useGet("/api/dashboard/incident-trends", { days: 30 });
  const alerts = useGet("/api/dashboard/recent-alerts", { limit: 12 }, { refetchMs: 20000 });
  const { feed } = useLive();
  const depts = useMemo(() => { const m = new Map<number, string>(); (machines.data?.items || []).forEach((x: any) => x.department_id && m.set(x.department_id, x.department)); return [...m]; }, [machines.data]);
  const ovd = ov.data;
  const scoreTone = !ovd ? undefined : ovd.safety_score >= 80 ? "ok" : ovd.safety_score >= 60 ? "warn" : "danger";
  const dist = ovd ? Object.entries(ovd.risk_distribution).map(([k, v]) => ({ name: k, value: v as number })) : [];
  const fmt = hours <= 24 ? hhmm : hours <= 168 ? ddhh : dd;
  const merged = useMemo(() => [...feed.slice(0, 6).map((f) => ({ k: f.id, level: f.level, title: f.text, ts: f.time, live: true })), ...(alerts.data || []).map((a: any, i: number) => ({ k: `r${i}`, level: a.level, title: a.title, ts: a.timestamp, live: false }))].slice(0, 12), [feed, alerts.data]);

  return (
    <>
      <PageHeader title="Executive Intelligence Dashboard" sub="What is happening in the facility, which machines are becoming dangerous, and how urgently to respond. All values are computed from backend records."
        actions={<>
          <Select aria-label="Time range" value={hours} onChange={(e) => setHours(+e.target.value)} className="w-32"><option value={6}>Last 6 h</option><option value={24}>Last 24 h</option><option value={168}>Last 7 d</option><option value={720}>Last 30 d</option></Select>
          <Select aria-label="Department" value={dept} onChange={(e) => { setDept(e.target.value); setMachine(""); }} className="w-40"><option value="">All departments</option>{depts.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</Select>
          <Select aria-label="Machine" value={machine} onChange={(e) => setMachine(e.target.value)} className="w-40"><option value="">All machines</option>{(machines.data?.items || []).filter((m: any) => !dept || String(m.department_id) === dept).map((m: any) => <option key={m.id} value={m.id}>{m.code}</option>)}</Select>
        </>} />
      <Async q={ov} skeleton={<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24" />)}</div>}>
        {(d) => (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat label="Safety score" value={d.safety_score} tone={scoreTone as any} icon={<ShieldCheck size={16} />} sub="Heuristic 0–100 (see definition in API)" />
            <Stat label="Machines" value={`${d.totals.machines_running}/${d.totals.machines}`} icon={<Cpu size={16} />} sub={`${d.totals.facilities} facilit${d.totals.facilities === 1 ? "y" : "ies"} · running / total`} />
            <Stat label="Active hazards" value={d.active_hazards} tone={d.active_hazards ? "orange" : "ok"} icon={<AlertTriangle size={16} />} sub="Machines High/Critical now" />
            <Stat label="Critical risk zones" value={d.critical_zone_count} tone={d.critical_zone_count ? "danger" : "ok"} icon={<Factory size={16} />} sub={d.critical_zones.join(", ") || "None"} />
            <Stat label="High/Critical predictions" value={d.accident_predictions.high_or_critical_in_window} icon={<TrendingUp size={16} />} sub={`of ${d.accident_predictions.total_in_window} in window`} />
            <Stat label="Near-miss reports" value={d.near_miss_reports} icon={<Siren size={16} />} sub={`${d.totals.open_incidents} open incidents`} />
            <Stat label="Maintenance alerts" value={d.maintenance_alerts.total} tone={d.maintenance_alerts.total ? "warn" : "ok"} icon={<Wrench size={16} />} sub={`${d.maintenance_alerts.overdue} overdue · ${d.maintenance_alerts.open_critical} critical open`} />
            <Stat label="Anomalies" value={d.anomalies_in_window} icon={<Zap size={16} />} sub="Isolation Forest + guard rail" />
          </div>
        )}
      </Async>

      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Historical risk trend" sub="Average and peak model probability of an event in the next ~6 h" right={<Select aria-label="Group by" value={group} onChange={(e) => setGroup(e.target.value)} className="w-36"><option value="fleet">Fleet</option><option value="department">By department</option><option value="machine">By machine</option></Select>} />
          <div className="p-3"><Async q={tr}>{(d) => d.points.length ? (
            <ChartBox h={260}>{group === "fleet" ? (
              <AreaChart data={d.points}><defs><linearGradient id="gf" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={C.accent} stopOpacity={0.4} /><stop offset="100%" stopColor={C.accent} stopOpacity={0} /></linearGradient></defs>
                {grid}<RX dataKey="timestamp" tickFormatter={fmt} {...axis} /><RY tickFormatter={(v) => pct(v, 0)} {...axis} width={44} />{tip}
                <Area dataKey="Fleet" name="Fleet average" stroke={C.accent} fill="url(#gf)" strokeWidth={2} formatter-value={undefined} /><Line dataKey="Fleet max" name="Peak machine" stroke={C.orange} dot={false} strokeWidth={1.5} /></AreaChart>
            ) : (
              <LineChart data={d.points}>{grid}<RX dataKey="timestamp" tickFormatter={fmt} {...axis} /><RY tickFormatter={(v) => pct(v, 0)} {...axis} width={44} />{tip}<Legend />
                {d.series_names.map((n: string, i: number) => <Line key={n} dataKey={n} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={1.6} connectNulls />)}</LineChart>
            )}</ChartBox>) : <Empty text="No predictions in this window" hint="Start the simulator or widen the time range." />}</Async></div>
        </Card>
        <Card>
          <CardHeader title="Live activity feed" sub="WebSocket events + recent alerts" right={<Bell size={15} className="text-muted" />} />
          <div className="max-h-[300px] divide-y divide-line/60 overflow-y-auto">
            {merged.length ? merged.map((a) => (
              <div key={a.k} className="flex items-start gap-2 px-4 py-2 text-sm"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: LVL[a.level] || C.accent }} /><div className="min-w-0 flex-1"><p className="truncate">{a.title}</p><p className="text-xs text-muted">{ago(a.ts)}{a.live && " · live"}</p></div></div>
            )) : <Empty text="No recent alerts" />}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardHeader title="Predicted risk — next 24 h" sub="Accident model applied to LSTM-forecast sensor values" />
          <div className="p-3"><Async q={pr}>{(d) => d.fleet_mean?.length ? (
            <ChartBox h={220}><LineChart data={d.hours.map((h: string, i: number) => ({ h, mean: d.fleet_mean[i], max: d.fleet_max[i] }))}>{grid}<RX dataKey="h" tickFormatter={hhmm} {...axis} /><RY tickFormatter={(v) => pct(v, 0)} {...axis} width={44} />{tip}<Legend />
              <Line dataKey="mean" name="Fleet mean" stroke={C.accent} dot={false} strokeWidth={2} /><Line dataKey="max" name="Highest machine" stroke={C.orange} dot={false} strokeWidth={2} strokeDasharray="4 3" /></LineChart></ChartBox>
          ) : <Empty text="Insufficient history for forecasting" hint="At least 24 contiguous hours of readings are required." />}</Async></div>
        </Card>
        <Card>
          <CardHeader title="Risk distribution" sub="Machines by current category" />
          <div className="p-3"><ChartBox h={220}><BarChart data={dist}>{grid}<RX dataKey="name" {...axis} /><RY allowDecimals={false} {...axis} width={30} />{tip}<Bar dataKey="value" name="Machines" radius={[6, 6, 0, 0]}>{dist.map((e) => <Cell key={e.name} fill={RISK_COLOR[e.name]} />)}</Bar></BarChart></ChartBox></div>
        </Card>
        <Card>
          <CardHeader title="Department comparison" sub="Average current risk" />
          <div className="p-3">{ovd?.risk_by_department?.length ? <ChartBox h={220}><BarChart data={ovd.risk_by_department} layout="vertical"><RX type="number" tickFormatter={(v) => pct(v, 0)} {...axis} /><RY type="category" dataKey="department" {...axis} width={80} />{tip}<Bar dataKey="avg_risk" name="Avg risk" fill={C.accent} radius={[0, 6, 6, 0]} /><Bar dataKey="max_risk" name="Max risk" fill={C.orange} radius={[0, 6, 6, 0]} /></BarChart></ChartBox> : <Empty />}</div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Incident history — 30 days" sub="Counts by severity" />
          <div className="p-3"><Async q={inc}>{(d) => <ChartBox h={220}><BarChart data={d}>{grid}<RX dataKey="date" tickFormatter={dd} {...axis} interval={4} /><RY allowDecimals={false} {...axis} width={30} />{tip}<Legend />
            {["low", "medium", "high", "critical"].map((s, i) => <Bar key={s} dataKey={s} stackId="a" fill={[C.ok, C.warn, C.orange, C.danger][i]} />)}</BarChart></ChartBox>}</Async></div>
        </Card>
        <Card>
          <CardHeader title="Machines needing attention" sub="Highest current risk (High/Critical)" />
          <div className="divide-y divide-line/60">
            {ovd?.hazard_machines?.length ? ovd.hazard_machines.map((m: any) => (
              <Link key={m.id} to={`/machines/${m.id}`} className="flex items-center justify-between px-4 py-2.5 text-sm hover:bg-surface2"><span><b>{m.code}</b> <span className="text-muted">{m.name}</span></span><span className="flex items-center gap-2">{pct(m.probability)} <RiskBadge level={m.category} /></span></Link>
            )) : <Empty text="No High/Critical machines" hint="Use Live Monitoring → inject an abnormal condition to test." />}
          </div>
        </Card>
      </div>
      <div className="mt-4"><Disclaimer>{ovd?.safety_score_definition || "Safety score is a heuristic summary, not a certified safety metric."} Predictions are statistical estimates from models trained on synthetic data.</Disclaimer></div>
    </>
  );
}
