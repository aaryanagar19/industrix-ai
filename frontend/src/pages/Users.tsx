import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Async, Badge, Button, Card, Empty, Field, Input, Modal, PageHeader, Pager, Select, Table, Tabs, useToast } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../services/api";
import { title, when } from "../utils/format";

export default function Users() {
  const { user: me } = useAuth(); const toast = useToast(); const qc = useQueryClient(); const [tab, setTab] = useState("users"); const [form, setForm] = useState<any>(null); const [page, setPage] = useState(1);
  const users = useGet<any[]>("/api/users"); const roles = useGet<any[]>("/api/roles"); const audit = useGet<any>("/api/audit", { page, page_size: 15 }, { enabled: tab === "audit" });
  const patch = useMutation({ mutationFn: ({ id, ...b }: any) => api.patch(`/api/users/${id}`, b), onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/users"] }); toast("User updated", "success"); }, onError: (e: any) => toast(e.message, "error") });
  const mk = useMutation({ mutationFn: (b: any) => api.post("/api/users", b), onSuccess: () => { qc.invalidateQueries({ queryKey: ["/api/users"] }); toast("User created", "success"); setForm(null); }, onError: (e: any) => toast(e.message, "error") });
  const submit = () => { if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email)) return toast("Enter a valid email", "warning"); if (form.password.length < 8) return toast("Password needs 8+ characters", "warning"); if (form.full_name.trim().length < 2) return toast("Enter a name", "warning"); mk.mutate(form); };
  return (
    <>
      <PageHeader title="User Management" sub="Role-based access control. Only Super Admins can manage users." actions={<Button onClick={() => setForm({ email: "", full_name: "", password: "", role: "plant_manager" })}><Plus size={15} />New user</Button>} />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "users", label: "Users" }, { id: "roles", label: "Role permissions" }, { id: "audit", label: "Audit log" }]} />
      {tab === "users" && <Card><Async q={users}>{(d) => <Table><thead><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th">Active</th><th className="th">Joined</th></tr></thead><tbody>{d.map((u: any) => <tr key={u.id} className="border-t border-line/60"><td className="td font-medium">{u.full_name}{u.id === me?.id && <Badge color="accent" className="ml-2">You</Badge>}</td><td className="td">{u.email}</td>
        <td className="td"><Select aria-label={`Role for ${u.email}`} className="w-48" value={u.role} disabled={u.id === me?.id} onChange={(e) => patch.mutate({ id: u.id, role: e.target.value })}>{roles.data?.map((r: any) => <option key={r.name} value={r.name}>{title(r.name)}</option>)}</Select></td>
        <td className="td"><input type="checkbox" aria-label={`Active ${u.email}`} checked={u.is_active} disabled={u.id === me?.id} onChange={(e) => patch.mutate({ id: u.id, is_active: e.target.checked })} /></td><td className="td">{when(u.created_at)}</td></tr>)}</tbody></Table>}</Async></Card>}
      {tab === "roles" && <div className="grid gap-3 md:grid-cols-2">{roles.data?.map((r: any) => <Card key={r.name} className="p-4"><b>{title(r.name)}</b><p className="mt-1 text-sm text-muted">{r.description}</p></Card>)}</div>}
      {tab === "audit" && <Card><Async q={audit}>{(d) => d.items.length ? <><Table><thead><tr><th className="th">Time</th><th className="th">User</th><th className="th">Action</th><th className="th">Entity</th><th className="th">Detail</th></tr></thead><tbody>{d.items.map((a: any) => <tr key={a.id} className="border-t border-line/60"><td className="td whitespace-nowrap">{when(a.created_at)}</td><td className="td">{a.user || "system"}</td><td className="td">{a.action}</td><td className="td">{a.entity} {a.entity_id}</td><td className="td max-w-xs truncate text-xs text-muted">{JSON.stringify(a.detail)}</td></tr>)}</tbody></Table><Pager page={page} total={d.total} size={15} onPage={setPage} /></> : <Empty />}</Async></Card>}
      <Modal open={!!form} onClose={() => setForm(null)} title="Create user">{form && <div className="space-y-3"><Field label="Full name"><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field><Field label="Email"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field><Field label="Temporary password"><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <Field label="Role"><Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{roles.data?.map((r: any) => <option key={r.name} value={r.name}>{title(r.name)}</option>)}</Select></Field><div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button><Button onClick={submit} loading={mk.isPending}>Create</Button></div></div>}</Modal>
    </>
  );
}
