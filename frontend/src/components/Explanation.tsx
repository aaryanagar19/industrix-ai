import { Bar, BarChart, Cell, XAxis as RX, YAxis as RY, ReferenceLine } from "recharts";
import { ChartBox, axis, grid, tip } from "./Charts";
import { Disclaimer, Table } from "./ui";
import { C, num } from "../utils/format";

export function ContributionChart({ items, h = 300 }: { items: any[]; h?: number }) {
  const data = items.slice(0, 10).map((c) => ({ name: c.label.replace(/ \(.*\)/, ""), shap: c.shap, value: c.value }));
  return (
    <ChartBox h={h}><BarChart data={data} layout="vertical" margin={{ left: 20 }}>{grid}<RX type="number" {...axis} /><RY type="category" dataKey="name" width={190} {...axis} />{tip}<ReferenceLine x={0} stroke={C.muted} />
      <Bar dataKey="shap" name="Contribution (log-odds)" radius={4}>{data.map((d, i) => <Cell key={i} fill={d.shap > 0 ? C.orange : C.ok} />)}</Bar></BarChart></ChartBox>
  );
}

export function BaselineTable({ rows }: { rows: any[] }) {
  return (
    <Table><thead><tr><th className="th">Parameter</th><th className="th">Current</th><th className="th">Normal range (±2σ)</th><th className="th">Deviation</th></tr></thead>
      <tbody>{rows.map((r) => <tr key={r.parameter} className="border-t border-line/60"><td className="td capitalize">{r.parameter.replace("_pct", "")}</td><td className="td tabular-nums">{num(r.value, 2)} {r.unit}</td><td className="td tabular-nums text-muted">{r.normal_low} – {r.normal_high}</td>
        <td className={`td tabular-nums font-medium ${Math.abs(r.deviation_sigma ?? 0) > 2 ? "text-danger" : ""}`}>{r.deviation_sigma == null ? "—" : `${r.deviation_sigma > 0 ? "+" : ""}${r.deviation_sigma}σ`}</td></tr>)}</tbody></Table>
  );
}

export function ExplanationView({ e, baseline }: { e: any; baseline?: any[] }) {
  if (!e) return null;
  return (
    <div className="space-y-4">
      <p className="text-sm">{e.summary}</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <div><p className="label">Feature contributions (orange raises risk, green lowers)</p><ContributionChart items={e.contributions} /></div>
        <div className="space-y-3 text-sm">
          <div><p className="label">Raised the estimate</p>{e.top_increasing.length ? <ul className="list-disc space-y-1 pl-5">{e.top_increasing.slice(0, 4).map((i: any) => <li key={i.feature}>{i.explanation}</li>)}</ul> : <p className="text-muted">Nothing above the fleet average.</p>}</div>
          <div><p className="label">Reduced the estimate</p>{e.top_decreasing.length ? <ul className="list-disc space-y-1 pl-5">{e.top_decreasing.slice(0, 3).map((i: any) => <li key={i.feature}>{i.explanation}</li>)}</ul> : <p className="text-muted">—</p>}</div>
        </div>
      </div>
      {baseline && <div><p className="label">Current readings vs this machine's baseline</p><BaselineTable rows={baseline} /></div>}
      <Disclaimer>{e.disclaimer}</Disclaimer>
    </div>
  );
}
