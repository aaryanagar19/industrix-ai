import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ReferenceArea, XAxis as RX, YAxis as RY } from "recharts";
import { Pause, Play, Plus, Zap } from "lucide-react";
import { Badge, Button, Card, CardHeader, Empty, Field, Input, Modal, PageHeader, RiskBadge, Select, SimBanner, StatusBadge, useToast } from "../components/ui";
import { ChartBox, axis, grid, tip, hhmm } from "../components/Charts";
import { useGet, useFacilities } from "../hooks/useApi";
import { useLive } from "../contexts/LiveContext";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { C, PARAMS, num, pct, title } from "../utils/format";

const KINDS = ["temperature_spike", "vibration_surge", "pressure_instability", "overload", "combined_fault"];
const TYPES = ["cnc_mill", "lathe", "grinder", "hydraulic_press", "furnace", "boiler", "compressor", "chiller", "pump", "conveyor", "robot", "packaging"];

function MachineChart({ m, param, hist }: { m: any; param: { key: string; label: string; unit: string }; hist: any[] }) {
  const b = m.baseline?.[param.key];
  const data = hist.map((r) => ({ t: r.timestamp, v: r[param.key] }));
  return (
    <Card className="p-3"><div className="mb-1 flex items-center justify-between text-xs"><b>{param.label}</b><span className="text-muted">{num(data.at(-1)?.v, 2)} {param.unit}</span></div>
      <ChartBox h={130}><LineChart data={data}>{grid}{b && <ReferenceArea y1={b.mean - 2 * b.std} y2={b.mean + 2 * b.std} fill={C.ok} fillOpacity={0.08} />}<RX dataKey="t" tickFormatter={hhmm} {...axis} minTickGap={40} /><RY domain={["auto", "auto"]} {...axis} width={38} tickFormatter={(v) => Number(v).toFixed(1)} />{tip}<Line dataKey="v" name={param.label} stroke={C.accent} dot={false} strokeWidth={1.8} isAnimationActive={false} /></LineChart></ChartBox></Card>
  );
}

export default function Monitoring() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient();
  const [sel, setSel] = useState<number | null>(null); const [q, setQ] = useState(""); const [risk, setRisk] = useState("");
  const [kind, setKind] = useState(KINDS[0]); const [dur, setDur] = useState(60); const [cascade, setCascade] = useState(false); const [add, setAdd] = useState(false);
  const machines = useGet<any>("/api/machines", { page_size: 200, q: q || undefined }, { refetchMs: 30000 });
  const live = useLive();
  const sim = useGet<any>("/api/simulator/status", undefined, { refetchMs: 4000 });
  const items: any[] = machines.data?.items || [];
  const rows = useMemo(() => items.map((m) => ({ ...m, r: live.readings[m.id] || m.latest_reading, p: live.predictions[m.id] ? { category: live.predictions[m.id].category, probability: live.predictions[m.id].probability } : m.risk })).filter((m) => !risk || m.p?.category === risk), [items, live.readings, live.predictions, risk]);
  const cur = rows.find((m) => m.id === (sel ?? rows[0]?.id));
  const histQ = useQuery({ queryKey: ["hist", cur?.id], queryFn: () => api.get(`/api/sensors/${cur!.id}/history`, { hours: 1, max_points: 200 }), enabled: !!cur, staleTime: 60000 });
  const hist = useMemo(() => {
    if (!cur) return [];
    const lv = live.history[cur.id] || []; const first = lv[0]?.timestamp;
    const old = (histQ.data?.points || []).filter((p: any) => !first || p.timestamp < first);
    return [...old, ...lv];
  }, [cur?.id, histQ.data, live.history]);
  const canOps = can("plant_manager", "safety_manager");
  const control = useMutation({ mutationFn: (b: any) => api.post("/api/simulator/control", b), onSuccess: () => qc.invalidateQueries({ queryKey: ["/api/simulator/status"] }), onError: (e: any) => toast(e.message, "error") });
  const inject = useMutation({ mutationFn: () => api.post("/api/simulator/inject", { machine_id: cur!.id, kind, duration_s: dur, cascade }), onSuccess: (r: any) => { toast(r.message, "warning"); qc.invalidateQueries({ queryKey: ["/api/simulator/status"] }); }, onError: (e: any) => toast(e.message, "error") });
  const clear = useMutation({ mutationFn: () => api.post("/api/simulator/clear"), onSuccess: () => { toast("Injected conditions cleared", "success"); qc.invalidateQueries({ queryKey: ["/api/simulator/status"] }); } });
  const s = sim.data;

  return (
    <>
      <PageHeader title="Live Industrial Monitoring" sub="Streaming sensor readings, current risk and controls for the built-in simulator." actions={can("plant_manager") && <Button onClick={() => setAdd(true)}><Plus size={15} />Add machine</Button>} />
      <SimBanner />
      <Card className="mt-4 p-3">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Badge color={s?.running ? "ok" : "warn"}>{s?.running ? "Simulator running" : "Simulator paused"}</Badge>
          <span className="text-muted">{live.connected ? "WebSocket connected" : "WebSocket reconnecting…"} · {live.messageCount} messages</span>
          {canOps ? (<div className="ml-auto flex flex-wrap items-center gap-2">
            <Button variant="ghost" onClick={() => control.mutate({ running: !s?.running })} disabled={!s}>{s?.running ? <><Pause size={14} />Pause</> : <><Play size={14} />Resume</>}</Button>
            <Select aria-label="Simulation speed" value={s?.speed ?? 1} onChange={(e) => control.mutate({ speed: +e.target.value })} className="w-28">{[0.5, 1, 2, 5, 10].map((v) => <option key={v} value={v}>{v}× speed</option>)}</Select>
          </div>) : <span className="ml-auto text-xs text-muted">Simulator controls require Plant/Safety Manager role</span>}
        </div>
        {canOps && cur && (
          <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-line pt-3">
            <div className="w-48"><span className="label">Inject test condition on {cur.code}</span><Select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((k) => <option key={k} value={k}>{title(k)}</option>)}</Select></div>
            <div className="w-24"><span className="label">Seconds</span><Input type="number" min={10} max={600} value={dur} onChange={(e) => setDur(+e.target.value)} /></div>
            <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={cascade} onChange={(e) => setCascade(e.target.checked)} />Cascade to dependents</label>
            <Button variant="danger" onClick={() => inject.mutate()} loading={inject.isPending}><Zap size={14} />Inject</Button>
            <Button variant="ghost" onClick={() => clear.mutate()}>Clear all</Button>
            {s?.active_injections?.length > 0 && <Badge color="warn">{s.active_injections.length} active: {s.active_injections.map((a: any) => `#${a.machine_id} ${a.remaining_s}s`).join(", ")}</Badge>}
          </div>
        )}
      </Card>

      <div className="mt-4 grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <div className="flex gap-2 border-b border-line p-3"><Input placeholder="Filter machines…" aria-label="Filter machines" value={q} onChange={(e) => setQ(e.target.value)} /><Select aria-label="Risk filter" value={risk} onChange={(e) => setRisk(e.target.value)} className="w-32"><option value="">All risk</option>{["Low", "Moderate", "High", "Critical"].map((r) => <option key={r}>{r}</option>)}</Select></div>
          <div className="max-h-[640px] divide-y divide-line/60 overflow-y-auto">
            {rows.length ? rows.map((m) => (
              <button key={m.id} onClick={() => setSel(m.id)} className={`block w-full px-4 py-3 text-left transition hover:bg-surface2 ${cur?.id === m.id ? "bg-accent/10" : ""}`}>
                <div className="flex items-center justify-between"><span className="text-sm font-semibold">{m.code} <span className="font-normal text-muted">{m.name}</span></span><RiskBadge level={m.p?.category} /></div>
                <div className="mt-1 flex items-center gap-3 text-xs text-muted"><span>{m.department}</span><StatusBadge s={m.status} /><span className="ml-auto tabular-nums text-ink">{pct(m.p?.probability)}</span></div>
                {m.r && <div className="mt-1.5 grid grid-cols-4 gap-1 text-[11px] tabular-nums text-muted"><span>{num(m.r.temperature, 1)}°C</span><span>{num(m.r.vibration, 2)}mm/s</span><span>{num(m.r.pressure, 1)}bar</span><span>{num(m.r.load_pct, 0)}%</span></div>}
              </button>
            )) : <Empty text="No machines match" />}
          </div>
        </Card>
        <div>
          {cur ? (<>
            <Card className="mb-4 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">{cur.code} — {cur.name}</h2><p className="text-xs text-muted">{cur.department} · {title(cur.machine_type)} · {num(cur.operating_hours, 0)} operating h · last reading source: <b>{cur.r?.data_source || "—"}</b></p></div><div className="flex items-center gap-2"><RiskBadge level={cur.p?.category} /><span className="text-xl font-semibold tabular-nums">{pct(cur.p?.probability)}</span><Link to={`/machines/${cur.id}`} className="btn-ghost">Details</Link></div></div></Card>
            <div className="grid gap-3 sm:grid-cols-2">{PARAMS.map((p) => <MachineChart key={p.key} m={cur} param={p} hist={hist} />)}</div>
            <p className="mt-2 text-xs text-muted">Green band = machine baseline ±2σ. Chart combines stored history (last hour) with live WebSocket points.</p>
          </>) : <Card><Empty text="Select a machine" /></Card>}
        </div>
      </div>
      <AddMachine open={add} onClose={() => setAdd(false)} />
    </>
  );
}

function AddMachine({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast(); const qc = useQueryClient(); const fac = useFacilities();
  const [f, setF] = useState<any>({ code: "", name: "", machine_type: "cnc_mill", install_year: 2020, department_id: "" });
  const [err, setErr] = useState("");
  const fid = fac.data?.[0]?.id;
  const dept = useGet<any>(`/api/facilities/${fid}`, undefined, { enabled: !!fid });
  const m = useMutation({ mutationFn: () => api.post("/api/machines", { ...f, facility_id: fid, department_id: f.department_id ? +f.department_id : null, install_year: +f.install_year }),
    onSuccess: () => { toast("Machine created", "success"); qc.invalidateQueries({ queryKey: ["/api/machines"] }); onClose(); setF({ ...f, code: "", name: "" }); }, onError: (e: any) => setErr(e.message) });
  const submit = () => { setErr(""); if (!/^[A-Za-z0-9\-_]{2,30}$/.test(f.code)) return setErr("Code: 2–30 letters, digits, - or _"); if (f.name.trim().length < 2) return setErr("Name is required"); m.mutate(); };
  return (
    <Modal open={open} onClose={onClose} title="Add machine">
      <div className="space-y-3">
        <Field label="Code"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="e.g. CN-03" /></Field>
        <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Type (sets normal baseline)"><Select value={f.machine_type} onChange={(e) => setF({ ...f, machine_type: e.target.value })}>{TYPES.map((t) => <option key={t} value={t}>{title(t)}</option>)}</Select></Field>
        <Field label="Department"><Select value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })}><option value="">Unassigned</option>{dept.data?.departments?.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></Field>
        <Field label="Install year"><Input type="number" value={f.install_year} onChange={(e) => setF({ ...f, install_year: e.target.value })} /></Field>
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={m.isPending}>Create</Button></div>
      </div>
    </Modal>
  );
}
