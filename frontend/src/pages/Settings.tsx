import { Fragment, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Moon, Sun } from "lucide-react";
import { Badge, Button, Card, CardHeader, Disclaimer, Field, Input, PageHeader, Select, useToast } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { api } from "../services/api";
import { title } from "../utils/format";

export default function Settings() {
  const { user, can, refresh } = useAuth(); const { theme, setTheme } = useTheme(); const toast = useToast(); const qc = useQueryClient();
  const thr = useGet<any>("/api/ai/thresholds"); const health = useGet<any>("/api/health"); const sim = useGet<any>("/api/simulator/status"); const perf = useGet<any>("/api/ai/model-performance");
  const [t, setT] = useState<any>(null); const cur = t ?? thr.data?.active;
  const saveT = useMutation({ mutationFn: () => api.put("/api/ai/thresholds", { moderate: +cur.moderate, high: +cur.high, critical: +cur.critical }), onSuccess: () => { toast("Thresholds saved (audit-logged)", "success"); setT(null); qc.invalidateQueries({ queryKey: ["/api/ai/thresholds"] }); }, onError: (e: any) => toast(e.message, "error") });
  const pref = useMutation({ mutationFn: (p: any) => api.patch("/api/auth/me/preferences", p), onSuccess: () => { refresh(); toast("Preference saved", "success"); }, onError: (e: any) => toast(e.message, "error") });
  const validT = () => { const a = +cur.moderate, b = +cur.high, c = +cur.critical; if (!(a > 0 && b > a && c > b && c < 1)) return toast("Thresholds must satisfy 0 < moderate < high < critical < 1", "warning"); saveT.mutate(); };
  return (
    <>
      <PageHeader title="Settings" sub="Personal preferences persist to your account. System settings require the appropriate role." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Profile & preferences" /><div className="space-y-4 p-4 text-sm"><p><b>{user?.full_name}</b><br /><span className="text-muted">{user?.email} · {title(user?.role)}</span></p>
          <Field label="Theme"><div className="flex gap-2"><Button variant={theme === "dark" ? "primary" : "ghost"} onClick={() => setTheme("dark")}><Moon size={14} />Dark</Button><Button variant={theme === "light" ? "primary" : "ghost"} onClick={() => setTheme("light")}><Sun size={14} />Light</Button></div></Field>
          <Field label="Default dashboard range" hint="Used when you open the dashboard."><Select value={user?.preferences?.default_hours ?? 24} onChange={(e) => pref.mutate({ default_hours: +e.target.value })}><option value={6}>Last 6 h</option><option value={24}>Last 24 h</option><option value={168}>Last 7 d</option><option value={720}>Last 30 d</option></Select></Field></div></Card>
        <Card><CardHeader title="Risk category thresholds" sub="Calibrated probability cut-offs. Learned from validation data; overridable here." />
          <div className="space-y-3 p-4">{cur && <div className="grid grid-cols-3 gap-3">{["moderate", "high", "critical"].map((k) => <Field key={k} label={k}><Input type="number" step="0.001" disabled={!can("safety_manager")} value={cur[k]} onChange={(e) => setT({ ...cur, [k]: e.target.value })} /></Field>)}</div>}
            <p className="text-xs text-muted">Trained defaults: {thr.data && `${thr.data.trained.moderate} / ${thr.data.trained.high} / ${thr.data.trained.critical}`}. Selection method: {perf.data?.threshold_method}</p>
            {can("safety_manager") ? <div className="flex gap-2"><Button onClick={validT} loading={saveT.isPending} disabled={!t}>Save thresholds</Button>{t && thr.data && <Button variant="ghost" onClick={() => setT(thr.data.trained)}>Reset to trained</Button>}</div> : <p className="text-xs text-muted">Only Safety Managers and Super Admins can change thresholds.</p>}</div></Card>
        <Card><CardHeader title="System status" /><dl className="grid grid-cols-2 gap-y-2 p-4 text-sm"><dt className="text-muted">API / database</dt><dd><Badge color={health.data?.status === "ok" ? "ok" : "danger"}>{health.data?.status ?? "…"}</Badge></dd>
          {health.data && Object.entries(health.data.models).map(([k, v]: any) => <Fragment key={k}><dt className="text-muted">Model: {k}</dt><dd><Badge color={v ? "ok" : "danger"}>{v ? "loaded" : "missing"}</Badge></dd></Fragment>)}
          <dt className="text-muted">Data source</dt><dd><Badge color="accent">{sim.data?.mode ?? "…"}</Badge> hardware connected: {String(sim.data?.hardware_connected)}</dd></dl></Card>
        <Card><CardHeader title="Model versions" /><div className="divide-y divide-line/60">{perf.data?.versions?.map((v: any, i: number) => <div key={i} className="flex items-center justify-between px-4 py-2 text-sm"><span>{v.name}<br /><span className="text-xs text-muted">{v.version}</span></span><span className="flex gap-1.5"><Badge color="warn">{v.data_origin}</Badge>{v.is_active && <Badge color="ok">active</Badge>}</span></div>)}</div></Card>
      </div>
      <div className="mt-4"><Disclaimer>INDUSTRIX AI is a decision-support prototype. It does not shut down machinery, control equipment or initiate physical emergency operations.</Disclaimer></div>
    </>
  );
}
