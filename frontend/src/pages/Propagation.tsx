import { useState } from "react";
import { Async, Card, CardHeader, Disclaimer, PageHeader, RiskBadge, Table } from "../components/ui";
import PlantMap from "../components/PlantMap";
import { useGet } from "../hooks/useApi";
import { pct } from "../utils/format";

export default function Propagation() {
  const q = useGet<any>("/api/risk/propagation", undefined, { refetchMs: 5000 }); const [sel, setSel] = useState<number | null>(null);
  return (
    <>
      <PageHeader title="Industrial Risk Propagation Map" sub="Local machine risk is combined with configured dependencies, historical co-occurrence and current anomalies to estimate how risk may spread to connected equipment." />
      <Async q={q}>{(d) => {
        const rows = [...d.nodes].sort((a: any, b: any) => b.propagated_risk - a.propagated_risk);
        const s = d.nodes.find((n: any) => n.id === sel);
        return (<>
          <Disclaimer><b>Analytical estimate, not a confirmed physical failure.</b> {d.disclaimer}</Disclaimer>
          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_340px]">
            <PlantMap data={d} mode="propagation" selected={sel} onSelect={setSel} showEdges />
            <Card><CardHeader title={s ? `${s.code} — ${s.name}` : "Selection"} sub="Click a machine" />
              {s ? <div className="space-y-2 p-4 text-sm"><p>Model probability: <b>{pct(s.model_probability)}</b></p><p>Local risk (incl. anomalies): <b>{pct(s.local_risk)}</b></p><p>Propagated risk: <b>{pct(s.propagated_risk)}</b> <RiskBadge level={s.category} /></p><p>Added by propagation: <b>+{pct(s.added_by_propagation, 2)}</b></p>
                <div><p className="label">Top upstream contributors</p>{s.upstream_contributors.length ? s.upstream_contributors.map((u: any) => <p key={u.machine_id}>{u.code} → +{pct(u.contribution, 2)}</p>) : <p className="text-muted">None above 0.5%</p>}</div></div> : <p className="p-4 text-sm text-muted">Edge thickness shows estimated risk flow; orange arrows carry more than 2%.</p>}
            </Card>
          </div>
          <Card className="mt-4"><CardHeader title="Ranking by propagated risk" sub="Formula: propagated = 1 − (1 − local) × Π(1 − edge strength × upstream risk), 2 hops" />
            <Table><thead><tr><th className="th">Machine</th><th className="th">Department</th><th className="th">Model P</th><th className="th">Local</th><th className="th">Propagated</th><th className="th">Added</th><th className="th">Category</th></tr></thead><tbody>{rows.map((n: any) => <tr key={n.id} className="cursor-pointer border-t border-line/60 hover:bg-surface2" onClick={() => setSel(n.id)}><td className="td"><b>{n.code}</b> {n.name}</td><td className="td">{n.department}</td><td className="td tabular-nums">{pct(n.model_probability)}</td><td className="td tabular-nums">{pct(n.local_risk)}</td><td className="td tabular-nums">{pct(n.propagated_risk)}</td><td className="td tabular-nums">{n.added_by_propagation > 0.0005 ? "+" + pct(n.added_by_propagation, 2) : "—"}</td><td className="td"><RiskBadge level={n.category} /></td></tr>)}</tbody></Table></Card>
          <Card className="mt-4"><CardHeader title="Configured dependencies" />
            <Table><thead><tr><th className="th">Source</th><th className="th">Target</th><th className="th">Relation</th><th className="th">Weight</th><th className="th">Co-occurrence (7 d)</th><th className="th">Strength</th><th className="th">Current flow</th></tr></thead><tbody>{d.edges.map((e: any, i: number) => { const s1 = d.nodes.find((n: any) => n.id === e.source), t1 = d.nodes.find((n: any) => n.id === e.target); return <tr key={i} className="border-t border-line/60"><td className="td">{s1?.code}</td><td className="td">{t1?.code}</td><td className="td">{e.relation}</td><td className="td tabular-nums">{e.weight}</td><td className="td tabular-nums">{e.cooccurrence}</td><td className="td tabular-nums">{e.strength}</td><td className="td tabular-nums">{pct(e.flow, 2)}</td></tr>; })}</tbody></Table></Card>
        </>);
      }}</Async>
    </>
  );
}
