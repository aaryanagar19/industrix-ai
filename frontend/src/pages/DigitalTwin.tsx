import { useState } from "react";
import { Link } from "react-router-dom";
import { Async, Badge, Card, CardHeader, Disclaimer, Empty, PageHeader, RiskBadge } from "../components/ui";
import PlantMap from "../components/PlantMap";
import { useGet } from "../hooks/useApi";
import { C, RISK_COLOR, pct, title } from "../utils/format";

export default function DigitalTwin() {
  const q = useGet<any>("/api/twin", undefined, { refetchMs: 5000 });
  const [sel, setSel] = useState<number | null>(null); const [edges, setEdges] = useState(true);
  return (
    <>
      <PageHeader title="Industrial Digital Twin" sub="Operational visualisation of the facility: zones, machines, dependencies, active anomalies and live risk levels. Click a machine or zone to inspect it." actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={edges} onChange={(e) => setEdges(e.target.checked)} />Show dependencies</label>} />
      <Async q={q}>{(d) => {
        const n = d.nodes.find((x: any) => x.id === sel);
        const zone = n && d.nodes.filter((x: any) => x.department_id === n.department_id);
        return (
          <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
            <div><PlantMap data={d} mode="twin" selected={sel} onSelect={setSel} showEdges={edges} />
              <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-muted">{["Low", "Moderate", "High", "Critical"].map((c) => <span key={c} className="flex items-center gap-1.5"><span className="h-3 w-3 rounded" style={{ background: RISK_COLOR[c] }} />{c}</span>)}<span className="flex items-center gap-1.5"><span className="grid h-4 w-4 place-items-center rounded-full bg-danger text-[10px] font-bold text-white">!</span>Active anomaly (15 min)</span><span>Pulsing = High/Critical</span></div></div>
            <Card><CardHeader title={n ? `${n.code} — ${n.name}` : "Inspector"} sub={n ? `${n.department} · ${title(n.type)}` : "Select a machine"} />
              {n ? <div className="space-y-3 p-4 text-sm"><div className="flex items-center gap-3"><span className="text-3xl font-semibold tabular-nums" style={{ color: RISK_COLOR[n.category] }}>{pct(n.model_probability)}</span><RiskBadge level={n.category} /></div>
                <dl className="grid grid-cols-2 gap-y-1"><dt className="text-muted">Anomaly level</dt><dd>{n.anomaly_level ? `${Math.round(n.anomaly_level * 100)}%` : "none"}</dd><dt className="text-muted">Propagated risk</dt><dd>{pct(n.propagated_risk)}</dd></dl>
                {n.upstream_contributors.length > 0 && <div><p className="label">Risk influenced by</p>{n.upstream_contributors.map((u: any) => <p key={u.machine_id}>{u.code}: +{pct(u.contribution)}</p>)}</div>}
                <div><p className="label">Zone: {n.department}</p><div className="flex flex-wrap gap-1.5">{zone.map((z: any) => <button key={z.id} onClick={() => setSel(z.id)} className="rounded-full border border-line px-2 py-0.5 text-xs hover:border-accent" style={{ color: RISK_COLOR[z.category] }}>{z.code}</button>)}</div></div>
                <Link to={`/machines/${n.id}`} className="btn-primary w-full">Open machine details</Link></div> : <Empty text="No machine selected" hint="Click a machine on the map." />}
            </Card>
          </div>);
      }}</Async>
      <div className="mt-4"><Disclaimer>This is an operational visualisation and risk-monitoring view. It does not simulate physical processes. Positions are schematic.</Disclaimer></div>
    </>
  );
}
