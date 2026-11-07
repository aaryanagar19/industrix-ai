import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FilePlus2 } from "lucide-react";
import { Async, Badge, Button, Card, CardHeader, Empty, Field, Input, PageHeader, Pager, Select, Table, useToast } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api, download } from "../services/api";
import { title, when } from "../utils/format";

export default function Reports() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient(); const [page, setPage] = useState(1);
  const [f, setF] = useState<any>({ report_type: "daily_safety", format: "pdf", days: "" });
  const list = useGet<any>("/api/reports", { page, page_size: 10 });
  const gen = useMutation({ mutationFn: () => api.post("/api/reports/generate", { report_type: f.report_type, format: f.format, days: f.days ? +f.days : null }), onSuccess: (r: any) => { toast("Report generated", "success"); qc.invalidateQueries({ queryKey: ["/api/reports"] }); download(`/api/reports/${r.id}/download`, `${r.report_type}.${r.format}`).catch(() => {}); }, onError: (e: any) => toast(e.message, "error") });
  const types = list.data?.types || {};
  return (
    <>
      <PageHeader title="Reports & Analytics" sub="Every report is generated from live database records and available as CSV or PDF." />
      {can("safety_manager", "plant_manager", "safety_officer") && <Card className="mb-4 p-4"><div className="flex flex-wrap items-end gap-3">
        <div className="w-64"><Field label="Report"><Select value={f.report_type} onChange={(e) => setF({ ...f, report_type: e.target.value })}>{Object.entries(types).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}</Select></Field></div>
        <div className="w-28"><Field label="Format"><Select value={f.format} onChange={(e) => setF({ ...f, format: e.target.value })}><option value="pdf">PDF</option><option value="csv">CSV</option></Select></Field></div>
        <div className="w-36"><Field label="Days (optional)"><Input type="number" min={1} max={366} placeholder="default" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} /></Field></div>
        <Button onClick={() => (f.days && (+f.days < 1 || +f.days > 366)) ? toast("Days must be 1–366", "warning") : gen.mutate()} loading={gen.isPending}><FilePlus2 size={15} />Generate & download</Button></div></Card>}
      <Card><CardHeader title="Generated reports" />
        <Async q={list}>{(d) => d.items.length ? <><Table><thead><tr><th className="th">Report</th><th className="th">Format</th><th className="th">Rows</th><th className="th">Generated</th><th className="th" /></tr></thead>
          <tbody>{d.items.map((r: any) => <tr key={r.id} className="border-t border-line/60"><td className="td font-medium">{r.title}</td><td className="td"><Badge color={r.format === "pdf" ? "accent" : "ok"}>{r.format.toUpperCase()}</Badge></td><td className="td tabular-nums">{r.row_count}</td><td className="td">{when(r.created_at)}</td><td className="td"><Button variant="ghost" className="px-2 py-1" onClick={() => download(`/api/reports/${r.id}/download`, `${r.report_type}_${r.id}.${r.format}`).catch((e) => toast(e.message, "error"))}><Download size={13} />Download</Button></td></tr>)}</tbody></Table>
          <Pager page={page} total={d.total} size={10} onPage={setPage} /></> : <Empty text="No reports generated yet" hint="Choose a report type above." />}</Async></Card>
    </>
  );
}
