import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCheck } from "lucide-react";
import { Async, Button, Card, Empty, PageHeader, Pager, Select } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { api } from "../services/api";
import { C, ago, title } from "../utils/format";

export default function Notifications() {
  const qc = useQueryClient(); const [level, setLevel] = useState(""); const [unread, setUnread] = useState(false); const [page, setPage] = useState(1);
  const q = useGet<any>("/api/notifications", { page, page_size: 15, level: level || undefined, unread: unread || undefined }, { refetchMs: 15000 });
  const inv = () => qc.invalidateQueries({ queryKey: ["notifications"] }) || qc.invalidateQueries({ queryKey: ["/api/notifications"] });
  const one = useMutation({ mutationFn: (id: number) => api.post(`/api/notifications/${id}/read`), onSuccess: inv });
  const all = useMutation({ mutationFn: () => api.post("/api/notifications/read-all"), onSuccess: inv });
  const col: Record<string, string> = { critical: C.danger, warning: C.warn, info: C.accent };
  return (
    <>
      <PageHeader title="Notification Center" sub="Alerts generated from real events: risk escalations, anomalies, incidents and maintenance assignments." actions={<>
        <Select aria-label="Level" className="w-32" value={level} onChange={(e) => { setLevel(e.target.value); setPage(1); }}><option value="">All levels</option>{["info", "warning", "critical"].map((l) => <option key={l} value={l}>{title(l)}</option>)}</Select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unread} onChange={(e) => { setUnread(e.target.checked); setPage(1); }} />Unread only</label>
        <Button variant="ghost" onClick={() => all.mutate()}><CheckCheck size={15} />Mark all read</Button></>} />
      <Card><Async q={q}>{(d) => d.items.length ? <><div className="divide-y divide-line/60">{d.items.map((n: any) => (
        <div key={n.id} className={`flex items-start gap-3 px-4 py-3 ${n.is_read ? "" : "bg-accent/5"}`}><span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: col[n.level] }} /><div className="min-w-0 flex-1"><p className="text-sm font-medium">{n.title}</p><p className="text-sm text-muted">{n.message}</p><p className="mt-0.5 text-xs text-muted">{title(n.kind)} · {ago(n.created_at)}</p></div>{!n.is_read && <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => one.mutate(n.id)}>Mark read</Button>}</div>))}</div>
        <Pager page={page} total={d.total} size={15} onPage={setPage} /></> : <Empty text="No notifications" />}</Async></Card>
    </>
  );
}
