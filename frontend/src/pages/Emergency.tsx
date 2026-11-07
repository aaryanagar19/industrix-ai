import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Settings2 } from "lucide-react";
import { Async, Badge, Button, Card, CardHeader, Disclaimer, Empty, Field, Input, Modal, PageHeader, RiskBadge, StatusBadge, useToast } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api, download } from "../services/api";
import { title, when } from "../utils/format";

export default function Emergency() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient(); const [sp, setSp] = useSearchParams();
  const id = sp.get("id"); const [action, setAction] = useState(""); const [resolve, setResolve] = useState<any>(null); const [resText, setResText] = useState(""); const [proc, setProc] = useState<any>(null);
  const list = useGet<any>("/api/incidents", { status: "active", page_size: 50 }, { refetchMs: 15000 });
  const det = useGet<any>(`/api/incidents/${id}`, undefined, { enabled: !!id, refetchMs: 15000 });
  const inv = () => { qc.invalidateQueries({ queryKey: [`/api/incidents/${id}`] }); qc.invalidateQueries({ queryKey: ["/api/incidents"] }); };
  const canWrite = can("safety_manager", "safety_officer");
  const patch = useMutation({ mutationFn: (b: any) => api.patch(`/api/incidents/${id}`, b), onSuccess: () => { toast("Incident updated", "success"); setResolve(null); inv(); }, onError: (e: any) => toast(e.message, "error") });
  const addAct = useMutation({ mutationFn: (a: string) => api.post(`/api/incidents/${id}/actions`, { action: a, category: "recorded", status: "done" }), onSuccess: () => { setAction(""); inv(); toast("Action recorded", "success"); }, onError: (e: any) => toast(e.message, "error") });
  const toggle = useMutation({ mutationFn: ({ aid, status }: any) => api.patch(`/api/incidents/${id}/actions/${aid}`, { status }), onSuccess: inv, onError: (e: any) => toast(e.message, "error") });
  const pr = useGet<any>("/api/incidents/procedures", undefined, { enabled: !!proc });
  const savePr = useMutation({ mutationFn: (b: any) => api.put("/api/incidents/procedures", b), onSuccess: () => { toast("Procedures saved", "success"); setProc(null); qc.invalidateQueries({ queryKey: ["/api/incidents/procedures"] }); }, onError: (e: any) => toast(e.message, "error") });
  const pdf = async () => { try { await download(`/api/incidents/${id}/report`, `incident_${id}_report.pdf`); } catch (e: any) { toast(e.message, "error"); } };
  return (
    <>
      <PageHeader title="Emergency Response Center" sub="Coordinate active incidents: review recommended actions, record what was actually done, and export the response report." actions={can("safety_manager") && <Button variant="ghost" onClick={() => setProc({})}><Settings2 size={15} />Edit procedures</Button>} />
      <Disclaimer><b>Decision support only.</b> Recommended actions are configurable templates that must follow approved facility procedures and be reviewed by authorised safety personnel. This system never replaces emergency services, certified safety officers or official evacuation procedures, and never operates machinery.</Disclaimer>
      <div className="mt-4 grid gap-4 xl:grid-cols-[320px_1fr]">
        <Card><CardHeader title="Active incidents" sub={`${list.data?.total ?? 0} open or responding`} />
          <div className="max-h-[620px] divide-y divide-line/60 overflow-y-auto">{list.data?.items?.length ? list.data.items.map((i: any) => <button key={i.id} onClick={() => setSp({ id: String(i.id) })} className={`block w-full px-4 py-3 text-left hover:bg-surface2 ${String(i.id) === id ? "bg-accent/10" : ""}`}><div className="flex items-center justify-between"><span className="text-sm font-medium">{i.title}</span><RiskBadge level={i.severity} /></div><div className="mt-1 flex items-center gap-2 text-xs text-muted"><StatusBadge s={i.status} />{i.machine_code}<span className="ml-auto">{when(i.occurred_at)}</span></div></button>) : <Empty text="No active incidents" hint="Resolved incidents can still be opened from the Incidents page." />}</div></Card>
        <div>{!id ? <Card><Empty text="Select an incident" /></Card> : <Async q={det}>{(d) => {
          const rec = d.actions.filter((a: any) => a.category === "recommended"), rcd = d.actions.filter((a: any) => a.category === "recorded"), ev = d.actions.filter((a: any) => a.category === "event");
          const timeline = [...d.actions].filter((a: any) => a.status === "done" || a.category === "event").sort((a: any, b: any) => (a.performed_at || a.created_at).localeCompare(b.performed_at || b.created_at));
          const active = d.status === "open" || d.status === "responding";
          return (<div className="space-y-4">
            <Card><CardHeader title={d.title} sub={`${title(d.incident_type)} · ${d.machine_code || "no machine"} · occurred ${when(d.occurred_at)}`} right={<div className="flex items-center gap-2"><RiskBadge level={d.severity} /><StatusBadge s={d.status} /></div>} />
              <div className="space-y-3 p-4 text-sm"><p>{d.description || "No description."}</p><p className="text-muted">Response team: {d.assigned_team || "not assigned"}</p>{d.resolution && <p><b>Resolution:</b> {d.resolution}</p>}
                <div className="flex flex-wrap gap-2">{canWrite && d.status === "open" && <Button onClick={() => patch.mutate({ status: "responding" })}>Start response</Button>}{canWrite && active && <Button variant="ghost" onClick={() => { setResText(d.resolution || ""); setResolve("resolved"); }}>Resolve…</Button>}{canWrite && d.status === "resolved" && <Button variant="ghost" onClick={() => patch.mutate({ status: "closed" })}>Close incident</Button>}
                  {can("safety_manager", "safety_officer", "plant_manager") && <Button variant="ghost" onClick={pdf}><Download size={14} />Export PDF report</Button>}</div></div></Card>
            <div className="grid gap-4 lg:grid-cols-2">
              <Card><CardHeader title="Recommended response checklist" sub="Templates — require authorised review" />
                <div className="divide-y divide-line/60">{rec.length ? rec.map((a: any) => <label key={a.id} className="flex items-start gap-3 px-4 py-2.5 text-sm"><input type="checkbox" className="mt-1" checked={a.status === "done"} disabled={!canWrite} onChange={(e) => toggle.mutate({ aid: a.id, status: e.target.checked ? "done" : "pending" })} /><span className={a.status === "done" ? "text-muted line-through" : ""}>{a.action}{a.performed_by && <span className="block text-xs text-muted">Confirmed by {a.performed_by} · {when(a.performed_at)}</span>}</span></label>) : <Empty text="No recommended actions" />}</div></Card>
              <Card><CardHeader title="Actions recorded by personnel" />
                <div className="divide-y divide-line/60">{rcd.length ? rcd.map((a: any) => <div key={a.id} className="px-4 py-2.5 text-sm">{a.action}<span className="block text-xs text-muted">{a.performed_by} · {when(a.performed_at || a.created_at)}</span></div>) : <Empty text="Nothing recorded yet" />}</div>
                {canWrite && active && <div className="flex gap-2 border-t border-line p-3"><Input aria-label="Record action" placeholder="Record an action taken…" value={action} onChange={(e) => setAction(e.target.value)} onKeyDown={(e) => e.key === "Enter" && action.trim().length >= 3 && addAct.mutate(action)} /><Button onClick={() => action.trim().length >= 3 ? addAct.mutate(action) : toast("Enter at least 3 characters", "warning")} loading={addAct.isPending}>Record</Button></div>}</Card>
            </div>
            <Card><CardHeader title="Incident timeline" /><ol className="space-y-3 p-4">{timeline.length ? timeline.map((a: any) => <li key={a.id} className="flex gap-3 text-sm"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-accent" /><div><p>{a.action}</p><p className="text-xs text-muted">{when(a.performed_at || a.created_at)} · {a.performed_by || "system"} · {a.category}</p></div></li>) : <Empty text="No timeline events" />}</ol></Card>
          </div>);
        }}</Async>}</div>
      </div>
      <Modal open={!!resolve} onClose={() => setResolve(null)} title="Resolve incident"><Field label="Resolution details (required)"><Input value={resText} onChange={(e) => setResText(e.target.value)} placeholder="Describe what resolved the incident" /></Field><div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setResolve(null)}>Cancel</Button><Button onClick={() => resText.trim().length < 3 ? toast("Resolution text is required", "warning") : patch.mutate({ status: "resolved", resolution: resText })} loading={patch.isPending}>Mark resolved</Button></div></Modal>
      <ProcedureEditor open={!!proc} data={pr.data?.procedures} onClose={() => setProc(null)} onSave={(b: any) => savePr.mutate(b)} saving={savePr.isPending} />
    </>
  );
}

function ProcedureEditor({ open, data, onClose, onSave, saving }: any) {
  const [draft, setDraft] = useState<Record<string, string> | null>(null);
  const cur = draft ?? Object.fromEntries(Object.entries(data || {}).map(([k, v]: any) => [k, v.join("\n")]));
  return (
    <Modal open={open} onClose={() => { setDraft(null); onClose(); }} title="Emergency procedure templates" wide>
      <p className="mb-3 text-xs text-muted">One step per line. Align with approved facility procedures; reviewed by authorised safety personnel.</p>
      <div className="max-h-[55vh] space-y-3 overflow-y-auto">{Object.keys(cur).map((k) => <Field key={k} label={title(k)}><textarea className="input min-h-[80px]" value={cur[k]} onChange={(e) => setDraft({ ...cur, [k]: e.target.value })} /></Field>)}</div>
      <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => { setDraft(null); onClose(); }}>Cancel</Button><Button loading={saving} onClick={() => onSave(Object.fromEntries(Object.entries(cur).map(([k, v]) => [k, (v as string).split("\n").map((s: string) => s.trim()).filter(Boolean)])))}>Save</Button></div>
    </Modal>
  );
}
