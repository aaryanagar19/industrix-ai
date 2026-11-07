import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, Legend, XAxis as RX, YAxis as RY } from "recharts";
import { Check, ScanSearch } from "lucide-react";
import { Button, Card, CardHeader, Empty, PageHeader, Pager, RiskBadge, Select, Table, useToast } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { ChartBox, axis, dd, ddhh, grid, tip } from "../components/Charts";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { C, num, title, when } from "../utils/format";

export default function Anomalies() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient();
  const [machine, setMachine] = useState(""); const [sev, setSev] = useState(""); const [param, setParam] = useState(""); const [hours, setHours] = useState(168); const [page, setPage] = useState(1); const [scan, setScan] = useState<any>(null);
  const list = useGet<any>("/api/ai/anomalies", { machine_id: machine || undefined, severity: sev || undefined, parameter: param || undefined, hours, page, page_size: 12 }, { refetchMs: 15000 });
  const trend = useGet<any>("/api/ai/anomalies/trend", { hours, machine_id: machine || undefined }, { refetchMs: 30000 });
  const ack = useMutation({ mutationFn: (id: number) => api.patch(`/api/ai/anomalies/${id}/acknowledge`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/ai/anomalies"] }); toast("Acknowledged", "success"); }, onError: (e: any) => toast(e.message, "error") });
  const run = useMutation({ mutationFn: () => api.post("/api/ai/anomaly-detection", { machine_id: +machine, hours: Math.min(hours, 168), persist: true }), onSuccess: (r) => { setScan(r); qc.invalidateQueries({ queryKey: ["/api/ai/anomalies"] }); toast(`Scanned ${r.scanned} readings, ${r.events.length} events`, "info"); }, onError: (e: any) => toast(e.message, "error") });
  const fmt = hours <= 72 ? ddhh : dd;
  return (
    <>
      <PageHeader title="Anomaly Detection" sub="Isolation Forest (unusual combinations) plus a z-score guard rail (large single-sensor excursions), evaluated against each machine's own baseline." />
      <Card className="mb-4 p-3"><div className="flex flex-wrap items-center gap-2">
        <MachinePicker allowAll value={machine} onChange={(v) => { setMachine(v); setPage(1); }} />
        <Select aria-label="Severity" value={sev} onChange={(e) => { setSev(e.target.value); setPage(1); }} className="w-36"><option value="">All severities</option>{["medium", "high", "critical"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
        <Select aria-label="Parameter" value={param} onChange={(e) => { setParam(e.target.value); setPage(1); }} className="w-40"><option value="">All parameters</option>{["temperature", "vibration", "pressure", "load_pct"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
        <Select aria-label="Range" value={hours} onChange={(e) => { setHours(+e.target.value); setPage(1); }} className="w-32"><option value={24}>24 h</option><option value={168}>7 d</option><option value={720}>30 d</option></Select>
        {can("plant_manager", "safety_manager", "safety_officer", "maintenance_engineer") && <Button variant="ghost" className="ml-auto" disabled={!machine} loading={run.isPending} onClick={() => run.mutate()}><ScanSearch size={15} />Re-scan selected machine</Button>}</div></Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><CardHeader title="Anomaly trend" sub="Count by severity" /><div className="p-3"><ChartBox h={240}><BarChart data={trend.data?.series || []}>{grid}<RX dataKey="bucket" tickFormatter={fmt} {...axis} /><RY allowDecimals={false} {...axis} width={30} />{tip}<Legend />{["medium", "high", "critical"].map((s, i) => <Bar key={s} dataKey={s} stackId="a" fill={[C.warn, C.orange, C.danger][i]} />)}</BarChart></ChartBox></div></Card>
        <Card><CardHeader title="By parameter" /><div className="p-3"><ChartBox h={240}><BarChart data={Object.entries(trend.data?.by_parameter || {}).map(([k, v]) => ({ k: title(k), v }))}>{grid}<RX dataKey="k" {...axis} /><RY allowDecimals={false} {...axis} width={30} />{tip}<Bar dataKey="v" name="Anomalies" fill={C.accent} radius={[6, 6, 0, 0]} /></BarChart></ChartBox></div></Card>
      </div>
      {scan && <Card className="mt-4 p-4 text-sm"><b>Scan result for {scan.machine_code}:</b> {scan.scanned} readings scanned · {scan.flagged} flagged · {scan.events.length} distinct events · {scan.saved} new records saved · {scan.method}</Card>}
      <Card className="mt-4"><CardHeader title="Anomaly history" />
        {list.data?.items?.length ? <><Table><thead><tr><th className="th">Time</th><th className="th">Machine</th><th className="th">Parameter</th><th className="th">Observed</th><th className="th">Expected range</th><th className="th">Score</th><th className="th">Severity</th><th className="th">Suggested investigation</th><th className="th" /></tr></thead>
          <tbody>{list.data.items.map((a: any) => <tr key={a.id} className="border-t border-line/60 align-top"><td className="td whitespace-nowrap">{when(a.timestamp)}</td><td className="td">{a.machine_code}</td><td className="td">{title(a.parameter)}</td><td className="td tabular-nums">{num(a.observed_value, 2)} {a.unit}</td><td className="td tabular-nums text-muted">{a.expected_low} – {a.expected_high}</td><td className="td tabular-nums">{num(a.score, 2)}</td><td className="td"><RiskBadge level={a.severity} /></td><td className="td max-w-xs text-xs text-muted">{a.suggestion}</td>
            <td className="td">{a.acknowledged ? <span className="text-xs text-ok">Acked</span> : <button aria-label="Acknowledge" className="btn-ghost px-2 py-1" onClick={() => ack.mutate(a.id)}><Check size={14} /></button>}</td></tr>)}</tbody></Table>
          <Pager page={page} total={list.data.total} size={12} onPage={setPage} /></> : <Empty text="No anomalies match" hint="Try widening the time range or injecting a test condition in Live Monitoring." />}
      </Card>
    </>
  );
}
