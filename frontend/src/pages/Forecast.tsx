import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Area, ComposedChart, Line, ReferenceLine, XAxis as RX, YAxis as RY } from "recharts";
import { LineChart as LC } from "lucide-react";
import { Badge, Button, Card, CardHeader, Disclaimer, Empty, PageHeader, Stat, Table, useToast } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { ChartBox, axis, ddhh, grid, tip } from "../components/Charts";
import { useGet } from "../hooks/useApi";
import { api } from "../services/api";
import { C, PARAMS } from "../utils/format";
import { useEffect } from "react";

export default function Forecast() {
  const [sp] = useSearchParams(); const toast = useToast(); const [machine, setMachine] = useState(sp.get("machine") || ""); const [res, setRes] = useState<any>(null);
  const perf = useGet<any>("/api/ai/model-performance");
  const run = useMutation({ mutationFn: () => api.post("/api/ai/forecast", { machine_id: +machine }), onSuccess: setRes, onError: (e: any) => toast(e.message, "error") });
  useEffect(() => { if (machine) run.mutate(); }, [machine]);
  const suff = res?.data_sufficiency;
  const merged = (p: string) => {
    if (!res) return [];
    const hist = res.history.map((h: any) => ({ t: h.timestamp, hist: h[p] }));
    const f = res.forecast.map((x: any) => ({ t: x.timestamp, fc: x[p], band: [x[`${p}_lower`], x[`${p}_upper`]] }));
    if (hist.length && f.length) f.unshift({ t: hist.at(-1).t, fc: hist.at(-1).hist, band: [hist.at(-1).hist, hist.at(-1).hist] });
    return [...hist, ...f];
  };
  const tm = perf.data?.forecast?.test_metrics;
  return (
    <>
      <PageHeader title="Risk Forecasting (LSTM)" sub="Multivariate LSTM trained on chronologically ordered hourly data predicts the next 24 h of temperature, vibration, pressure and load. Shaded bands are ±1.96σ of held-out residuals." actions={<><MachinePicker value={machine} onChange={setMachine} /><Button onClick={() => run.mutate()} disabled={!machine} loading={run.isPending}><LC size={15} />Forecast</Button></>} />
      {!machine && <Card><Empty text="Select a machine to generate a forecast" /></Card>}
      {res && (<>
        {suff.status !== "ok" && <div className="mb-4"><Disclaimer><b>Data sufficiency: {suff.status}.</b> {suff.message}</Disclaimer></div>}
        {res.health_indicator && <div className="mb-4 grid gap-4 sm:grid-cols-3"><Stat label="Health indicator now" value={res.health_indicator.current} tone={res.health_indicator.current > 80 ? "ok" : "warn"} sub="Heuristic index (0–100)" /><Stat label="Health indicator +24 h" value={res.health_indicator.forecast_24h} tone={res.health_indicator.forecast_24h > 80 ? "ok" : "warn"} sub="From forecast deviations" /><Stat label="Early warnings" value={res.early_warnings.length} tone={res.early_warnings.length ? "danger" : "ok"} sub={res.early_warnings.length ? "Forecast leaves normal range" : "None in next 24 h"} /></div>}
        {res.early_warnings.length > 0 && <div className="mb-4 space-y-2">{res.early_warnings.map((w: any) => <Disclaimer key={w.parameter}><b>Early warning ·</b> {w.message}</Disclaimer>)}</div>}
        {res.forecast.length > 0 ? <div className="grid gap-4 lg:grid-cols-2">{PARAMS.map((p) => (
          <Card key={p.key}><CardHeader title={`${p.label} (${p.unit})`} sub="History vs. forecast with uncertainty band" />
            <div className="p-3"><ChartBox h={230}><ComposedChart data={merged(p.key)}>{grid}<RX dataKey="t" tickFormatter={ddhh} {...axis} minTickGap={50} /><RY domain={["auto", "auto"]} {...axis} width={44} tickFormatter={(v) => Number(v).toFixed(1)} />{tip}
              <Area dataKey="band" name="95% band" stroke="none" fill={C.accent} fillOpacity={0.15} /><Line dataKey="hist" name="Historical" stroke={C.ink} dot={false} strokeWidth={1.6} connectNulls /><Line dataKey="fc" name="Forecast" stroke={C.accent} strokeDasharray="5 3" dot={false} strokeWidth={2} connectNulls />
              {res.history.length > 0 && <ReferenceLine x={res.history.at(-1).timestamp} stroke={C.muted} strokeDasharray="2 2" label={{ value: "now", fill: C.muted, fontSize: 10 }} />}</ComposedChart></ChartBox></div></Card>))}</div> : <Card><Empty text="No forecast shown" hint={suff?.message} /></Card>}
        <p className="mt-3 text-xs text-muted">{res.disclaimer} Model {res.model_version}.</p>
      </>)}
      {tm && <Card className="mt-6"><CardHeader title="Forecast model evaluation" sub="Held-out chronological segment of SYNTHETIC data · MAE in σ units (lower is better)" />
        <Table><thead><tr><th className="th">Model</th>{Object.keys(tm.lstm.mae).map((k) => <th key={k} className="th">{k.replace("_dev", "")}</th>)}</tr></thead><tbody>
          {[["LSTM", tm.lstm], ["Baseline: always at normal", tm.baseline_zero], ["Persistence (repeat last value)", tm.persistence_baseline]].map(([n, m]: any) => <tr key={n} className="border-t border-line/60"><td className="td">{n}</td>{Object.values(m.mae).map((v: any, i) => <td key={i} className="td tabular-nums">{v}</td>)}</tr>)}</tbody></Table>
        <p className="px-4 pb-3 text-xs text-muted">The gain over the “always normal” baseline is modest because most variation in the synthetic data is random noise; the LSTM mainly captures daily load cycles and degradation ramps. <Badge color="warn">Synthetic</Badge></p></Card>}
    </>
  );
}
