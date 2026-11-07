import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Play, Plus, Wand2 } from "lucide-react";
import { Async, Badge, Button, Card, CardHeader, Empty, Field, Input, Modal, PageHeader, Pager, RiskBadge, Select, Stat, StatusBadge, Table, Tabs, useToast } from "../components/ui";
import MachinePicker from "../components/MachinePicker";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { pct, title, when } from "../utils/format";

const dueIso = (days: number) => new Date(Date.now() + days * 86400000).toISOString();

export default function Maintenance() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient();
  const [tab, setTab] = useState("tasks"); const [f, setF] = useState<any>({ status: "", priority: "", machine_id: "", overdue: false, q: "" }); const [page, setPage] = useState(1);
  const [create, setCreate] = useState<any>(null); const [done, setDone] = useState<any>(null); const [notes, setNotes] = useState("");
  const params = { page, page_size: 10, status: f.status || undefined, priority: f.priority || undefined, machine_id: f.machine_id || undefined, overdue: f.overdue || undefined, q: f.q || undefined };
  const tasks = useGet<any>("/api/maintenance", params, { refetchMs: 20000 });
  const sum = useGet<any>("/api/maintenance/summary", undefined, { refetchMs: 20000 });
  const users = useGet<any[]>("/api/users");
  const recs = useGet<any>("/api/maintenance/recommendations", undefined, { enabled: can("plant_manager", "safety_manager") && tab === "recs" });
  const insp = useGet<any[]>("/api/maintenance/inspections", undefined, { enabled: tab === "insp" });
  const inv = () => { qc.invalidateQueries({ queryKey: ["/api/maintenance"] }); qc.invalidateQueries({ queryKey: ["/api/maintenance/summary"] }); qc.invalidateQueries({ queryKey: ["/api/maintenance/recommendations"] }); };
  const mk = useMutation({ mutationFn: (b: any) => api.post("/api/maintenance", b), onSuccess: () => { toast("Task created", "success"); setCreate(null); inv(); }, onError: (e: any) => toast(e.message, "error") });
  const up = useMutation({ mutationFn: ({ id, ...b }: any) => api.patch(`/api/maintenance/${id}`, b), onSuccess: () => { toast("Task updated", "success"); setDone(null); setNotes(""); inv(); }, onError: (e: any) => toast(e.message, "error") });
  const canCreate = can("safety_manager", "plant_manager"); const canAssign = canCreate;
  const submitCreate = () => { if (!create.machine_id) return toast("Select a machine", "warning"); if ((create.title || "").trim().length < 3) return toast("Title must be at least 3 characters", "warning"); mk.mutate({ ...create, machine_id: +create.machine_id, assigned_to_id: create.assigned_to_id ? +create.assigned_to_id : null, due_date: create.due_date ? new Date(create.due_date).toISOString() : null }); };
  return (
    <>
      <PageHeader title="Preventive Maintenance Intelligence" sub="Schedule, assign and complete maintenance. Recommendations are heuristic scores combining risk, anomalies, service age and inspections." actions={canCreate && <Button onClick={() => setCreate({ title: "", priority: "medium", maint_type: "preventive", machine_id: "", description: "", due_date: "" })}><Plus size={15} />New task</Button>} />
      <div className="mb-4 grid gap-4 sm:grid-cols-4"><Stat label="Scheduled" value={sum.data?.scheduled ?? "—"} tone="accent" /><Stat label="In progress" value={sum.data?.in_progress ?? "—"} tone="warn" /><Stat label="Overdue" value={sum.data?.overdue ?? "—"} tone={sum.data?.overdue ? "danger" : "ok"} /><Stat label="Completed" value={sum.data?.completed ?? "—"} tone="ok" /></div>
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "tasks", label: "Tasks" }, ...(canCreate ? [{ id: "recs", label: "AI recommendations" }] : []), { id: "insp", label: "Inspections" }]} />
      {tab === "tasks" && <Card>
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3"><Input className="w-48" placeholder="Search tasks…" aria-label="Search tasks" value={f.q} onChange={(e) => { setF({ ...f, q: e.target.value }); setPage(1); }} />
          <Select aria-label="Status" className="w-36" value={f.status} onChange={(e) => { setF({ ...f, status: e.target.value }); setPage(1); }}><option value="">All status</option>{["scheduled", "in_progress", "completed", "cancelled"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
          <Select aria-label="Priority" className="w-32" value={f.priority} onChange={(e) => { setF({ ...f, priority: e.target.value }); setPage(1); }}><option value="">All priority</option>{["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{title(s)}</option>)}</Select>
          <MachinePicker allowAll value={f.machine_id} onChange={(v) => { setF({ ...f, machine_id: v }); setPage(1); }} className="w-44" />
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.overdue} onChange={(e) => { setF({ ...f, overdue: e.target.checked }); setPage(1); }} />Overdue only</label></div>
        <Async q={tasks}>{(d) => d.items.length ? <><Table><thead><tr><th className="th">Task</th><th className="th">Machine</th><th className="th">Priority</th><th className="th">Status</th><th className="th">Due</th><th className="th">Assigned</th><th className="th">Effectiveness</th><th className="th" /></tr></thead>
          <tbody>{d.items.map((t: any) => <tr key={t.id} className="border-t border-line/60 align-top"><td className="td"><b>{t.title}</b><br /><span className="text-xs text-muted">{title(t.maint_type)}{t.source === "ai_recommendation" && " · AI-recommended"}</span></td><td className="td">{t.machine_code}</td><td className="td"><RiskBadge level={t.priority} /></td>
            <td className="td"><StatusBadge s={t.status} />{t.is_overdue && <Badge color="danger" className="ml-1">Overdue</Badge>}</td><td className="td whitespace-nowrap">{when(t.due_date)}</td>
            <td className="td">{canAssign && t.status !== "completed" ? <Select aria-label="Assign" className="w-36" value={t.assigned_to_id ?? ""} onChange={(e) => up.mutate({ id: t.id, assigned_to_id: e.target.value ? +e.target.value : null })}><option value="">Unassigned</option>{users.data?.filter((u: any) => ["maintenance_engineer", "plant_manager", "safety_manager"].includes(u.role)).map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select> : t.assigned_to || "—"}</td>
            <td className="td text-xs">{t.effectiveness ? <span title={t.effectiveness.note}>{pct(t.effectiveness.risk_before)} → {pct(t.effectiveness.risk_after)} ({t.effectiveness.change_pct > 0 ? "+" : ""}{t.effectiveness.change_pct}%)</span> : "—"}</td>
            <td className="td whitespace-nowrap">{t.status === "scheduled" && <Button variant="ghost" className="px-2 py-1" onClick={() => up.mutate({ id: t.id, status: "in_progress" })}><Play size={13} />Start</Button>}{(t.status === "scheduled" || t.status === "in_progress") && <Button variant="ghost" className="ml-1 px-2 py-1" onClick={() => setDone(t)}><CheckCircle2 size={13} />Complete</Button>}</td></tr>)}</tbody></Table>
          <Pager page={page} total={d.total} size={10} onPage={setPage} /></> : <Empty text="No tasks match your filters" />}</Async>
      </Card>}
      {tab === "recs" && <Card><CardHeader title="Recommended preventive actions" sub={recs.data?.method} />
        <Async q={recs}>{(d) => d.items.length ? <div className="divide-y divide-line/60">{d.items.map((r: any) => <div key={r.machine_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"><div><p className="text-sm font-semibold">{r.machine_code} — {r.machine_name} <RiskBadge level={r.priority} /></p><ul className="mt-1 list-disc pl-5 text-xs text-muted">{r.reasons.map((x: string) => <li key={x}>{x}</li>)}</ul></div>
          <Button onClick={() => mk.mutate({ machine_id: r.machine_id, title: r.suggested_title, priority: r.priority, maint_type: "preventive", source: "ai_recommendation", description: `Reasons: ${r.reasons.join("; ")}`, due_date: dueIso(r.suggested_due_days) })} loading={mk.isPending}><Wand2 size={14} />Schedule</Button></div>)}</div> : <Empty text="No recommendations right now" hint="Machines with open tasks or low scores are skipped." />}</Async></Card>}
      {tab === "insp" && <Card><CardHeader title="Inspection records" /><Async q={insp}>{(d) => d.length ? <Table><thead><tr><th className="th">Date</th><th className="th">Machine</th><th className="th">Result</th><th className="th">Notes</th></tr></thead><tbody>{d.map((i: any) => <tr key={i.id} className="border-t border-line/60"><td className="td">{when(i.inspected_at)}</td><td className="td">{i.machine_code}</td><td className="td"><RiskBadge level={i.status === "fail" ? "Critical" : i.status === "conditional" ? "Moderate" : "Low"} /> {i.status}</td><td className="td text-muted">{i.notes}</td></tr>)}</tbody></Table> : <Empty text="No inspections" />}</Async></Card>}

      <Modal open={!!create} onClose={() => setCreate(null)} title="New maintenance task" wide>{create && <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Machine"><MachinePicker value={String(create.machine_id)} onChange={(v) => setCreate({ ...create, machine_id: v })} className="w-full" /></Field>
        <Field label="Title"><Input value={create.title} onChange={(e) => setCreate({ ...create, title: e.target.value })} /></Field>
        <Field label="Type"><Select value={create.maint_type} onChange={(e) => setCreate({ ...create, maint_type: e.target.value })}>{["preventive", "corrective", "inspection"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="Priority"><Select value={create.priority} onChange={(e) => setCreate({ ...create, priority: e.target.value })}>{["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="Due date"><Input type="datetime-local" value={create.due_date} onChange={(e) => setCreate({ ...create, due_date: e.target.value })} /></Field>
        <Field label="Assign to"><Select value={create.assigned_to_id ?? ""} onChange={(e) => setCreate({ ...create, assigned_to_id: e.target.value })}><option value="">Unassigned</option>{users.data?.map((u: any) => <option key={u.id} value={u.id}>{u.full_name} ({title(u.role)})</option>)}</Select></Field>
        <div className="sm:col-span-2"><Field label="Description"><Input value={create.description} onChange={(e) => setCreate({ ...create, description: e.target.value })} /></Field></div>
        <div className="flex justify-end gap-2 sm:col-span-2"><Button variant="ghost" onClick={() => setCreate(null)}>Cancel</Button><Button onClick={submitCreate} loading={mk.isPending}>Create task</Button></div></div>}</Modal>
      <Modal open={!!done} onClose={() => setDone(null)} title={`Complete: ${done?.title ?? ""}`}><Field label="Completion notes"><Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What was done?" /></Field><div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setDone(null)}>Cancel</Button><Button onClick={() => up.mutate({ id: done.id, status: "completed", completion_notes: notes })} loading={up.isPending}>Mark completed</Button></div></Modal>
    </>
  );
}
