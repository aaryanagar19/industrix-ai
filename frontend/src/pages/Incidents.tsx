import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Async, Button, Card, Empty, Field, Input, Modal, PageHeader, Pager, RiskBadge, Select, StatusBadge, Table, useToast } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { title, when } from "../utils/format";

export const INC_TYPES = ["equipment_failure", "fire_overheat", "leak_spill", "electrical", "near_miss", "personal_injury", "other"];

export default function Incidents() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient(); const nav = useNavigate();
  const [f, setF] = useState<any>({ q: "", status: "", severity: "", incident_type: "" }); const [page, setPage] = useState(1); const [form, setForm] = useState<any>(null);
  const q = useGet<any>("/api/incidents", { page, page_size: 12, q: f.q || undefined, status: f.status || undefined, severity: f.severity || undefined, incident_type: f.incident_type || undefined }, { refetchMs: 20000 });
  const mk = useMutation({ mutationFn: (b: any) => api.post("/api/incidents", b), onSuccess: (r: any) => { toast("Incident created — recommended actions generated for review", "success"); setForm(null); qc.invalidateQueries({ queryKey: ["/api/incidents"] }); nav(`/emergency?id=${r.id}`); }, onError: (e: any) => toast(e.message, "error") });
  const submit = () => { if ((form.title || "").trim().length < 3) return toast("Title must be at least 3 characters", "warning"); mk.mutate({ ...form, machine_id: form.machine_id ? +form.machine_id : null }); };
  const set = (k: string, v: any) => { setF({ ...f, [k]: v }); setPage(1); };
  return (
    <>
      <PageHeader title="Incident Management" sub="Report, classify and track incidents and near-misses." actions={can("safety_manager", "safety_officer") && <Button onClick={() => setForm({ title: "", description: "", incident_type: "equipment_failure", severity: "medium", machine_id: "", assigned_team: "" })}><Plus size={15} />Report incident</Button>} />
      <Card><div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
        <Input className="w-56" aria-label="Search incidents" placeholder="Search incidents…" value={f.q} onChange={(e) => set("q", e.target.value)} />
        <Select aria-label="Status" className="w-36" value={f.status} onChange={(e) => set("status", e.target.value)}><option value="">All status</option><option value="active">Active</option>{["open", "responding", "resolved", "closed"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
        <Select aria-label="Severity" className="w-36" value={f.severity} onChange={(e) => set("severity", e.target.value)}><option value="">All severity</option>{["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
        <Select aria-label="Type" className="w-44" value={f.incident_type} onChange={(e) => set("incident_type", e.target.value)}><option value="">All types</option>{INC_TYPES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select></div>
        <Async q={q}>{(d) => d.items.length ? <><Table><thead><tr><th className="th">Occurred</th><th className="th">Title</th><th className="th">Type</th><th className="th">Machine</th><th className="th">Severity</th><th className="th">Status</th></tr></thead>
          <tbody>{d.items.map((i: any) => <tr key={i.id} className="cursor-pointer border-t border-line/60 hover:bg-surface2" onClick={() => nav(`/emergency?id=${i.id}`)}><td className="td whitespace-nowrap">{when(i.occurred_at)}</td><td className="td font-medium">{i.title}</td><td className="td">{title(i.incident_type)}</td><td className="td">{i.machine_code || "—"}</td><td className="td"><RiskBadge level={i.severity} /></td><td className="td"><StatusBadge s={i.status} /></td></tr>)}</tbody></Table>
          <Pager page={page} total={d.total} size={12} onPage={setPage} /></> : <Empty text="No incidents match" />}</Async></Card>
      <Modal open={!!form} onClose={() => setForm(null)} title="Report incident" wide>{form && <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2"><Field label="Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field></div>
        <Field label="Type"><Select value={form.incident_type} onChange={(e) => setForm({ ...form, incident_type: e.target.value })}>{INC_TYPES.map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select></Field>
        <Field label="Severity"><Select value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>{["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="Affected machine"><MachinePicker allowAll value={String(form.machine_id)} onChange={(v) => setForm({ ...form, machine_id: v })} className="w-full" /></Field>
        <Field label="Assigned response team"><Input value={form.assigned_team} onChange={(e) => setForm({ ...form, assigned_team: e.target.value })} /></Field>
        <div className="sm:col-span-2"><Field label="Description"><Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button><Button onClick={submit} loading={mk.isPending}>Create incident</Button></div></div>}</Modal>
    </>
  );
}
