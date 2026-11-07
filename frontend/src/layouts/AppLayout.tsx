import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Activity, AlertOctagon, Bell, Box, ChevronRight, FileText, FileSearch, Gauge, LayoutDashboard, LineChart, LogOut, Menu, Moon, Network, Radar, ScanSearch, Search, Settings, ShieldAlert, Siren, Sun, Users, Wrench, X } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { useLive } from "../contexts/LiveContext";
import { useTheme } from "../contexts/ThemeContext";
import { api } from "../services/api";
import { ago, title } from "../utils/format";
import { Badge, Dot } from "../components/ui";

const NAV = [
  { to: "/", label: "Executive Dashboard", icon: LayoutDashboard, end: true },
  { to: "/monitoring", label: "Live Monitoring", icon: Activity },
  { to: "/prediction", label: "AI Prediction", icon: Gauge },
  { to: "/forecast", label: "Risk Forecast", icon: LineChart },
  { to: "/anomalies", label: "Anomaly Detection", icon: Radar },
  { to: "/explain", label: "Explainable AI", icon: ScanSearch },
  { to: "/twin", label: "Digital Twin", icon: Box },
  { to: "/propagation", label: "Risk Propagation", icon: Network },
  { to: "/maintenance", label: "Maintenance", icon: Wrench },
  { to: "/incidents", label: "Incidents", icon: AlertOctagon },
  { to: "/emergency", label: "Emergency Center", icon: Siren },
  { to: "/documents", label: "Document Intelligence", icon: FileSearch },
  { to: "/reports", label: "Reports & Analytics", icon: FileText },
  { to: "/notifications", label: "Notifications", icon: Bell },
  { to: "/users", label: "User Management", icon: Users, roles: ["super_admin"] },
  { to: "/settings", label: "Settings", icon: Settings },
];

function useCrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  const labels: Record<string, string> = Object.fromEntries(NAV.map((n) => [n.to.slice(1), n.label]));
  labels.machines = "Machines";
  return [{ to: "/", label: "Home" }, ...parts.map((p, i) => ({ to: "/" + parts.slice(0, i + 1).join("/"), label: labels[p] || (/^\d+$/.test(p) ? `#${p}` : title(p)) }))];
}

function SearchBox() {
  const [q, setQ] = useState(""); const [open, setOpen] = useState(false); const nav = useNavigate(); const ref = useRef<HTMLDivElement>(null);
  const [dq, setDq] = useState("");
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 250); return () => clearTimeout(t); }, [q]);
  const res = useQuery({ queryKey: ["search", dq], queryFn: () => api.get("/api/search", { q: dq }), enabled: dq.length >= 2 });
  useEffect(() => { const f = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false); document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, []);
  const go = (to: string) => { nav(to); setOpen(false); setQ(""); };
  const d = res.data;
  const empty = d && !d.machines.length && !d.incidents.length && !d.maintenance.length && !d.documents.length;
  return (
    <div ref={ref} className="relative w-full max-w-sm">
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
      <input aria-label="Search" className="input pl-9" placeholder="Search machines, incidents, tasks, documents…" value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
      {open && dq.length >= 2 && (
        <div className="card absolute left-0 right-0 top-11 z-40 max-h-96 overflow-y-auto p-2 text-sm shadow-xl">
          {res.isLoading && <p className="p-2 text-muted">Searching…</p>}
          {empty && <p className="p-2 text-muted">No results for “{dq}”</p>}
          {d?.machines.map((m: any) => <button key={"m" + m.id} onClick={() => go(`/machines/${m.id}`)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface2"><Badge color="accent">Machine</Badge>{m.code} — {m.name}</button>)}
          {d?.incidents.map((m: any) => <button key={"i" + m.id} onClick={() => go(`/emergency?id=${m.id}`)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface2"><Badge color="danger">Incident</Badge>{m.title}</button>)}
          {d?.maintenance.map((m: any) => <button key={"t" + m.id} onClick={() => go(`/maintenance`)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface2"><Badge color="warn">Task</Badge>{m.title}</button>)}
          {d?.documents.map((m: any) => <button key={"d" + m.id} onClick={() => go(`/documents?id=${m.id}`)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-surface2"><Badge>Doc</Badge>{m.filename}</button>)}
        </div>
      )}
    </div>
  );
}

function Bell_() {
  const [open, setOpen] = useState(false); const qc = useQueryClient(); const nav = useNavigate(); const ref = useRef<HTMLDivElement>(null);
  const q = useQuery({ queryKey: ["notifications", "bell"], queryFn: () => api.get("/api/notifications", { page_size: 8 }), refetchInterval: 30000 });
  useEffect(() => { const f = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false); document.addEventListener("mousedown", f); return () => document.removeEventListener("mousedown", f); }, []);
  const unread = q.data?.unread ?? 0;
  return (
    <div ref={ref} className="relative">
      <button aria-label="Notifications" className="btn-ghost relative px-2.5" onClick={() => setOpen(!open)}><Bell size={16} />{unread > 0 && <span className="absolute -right-1 -top-1 min-w-[18px] rounded-full bg-danger px-1 text-center text-[10px] font-bold text-white">{unread > 99 ? "99+" : unread}</span>}</button>
      {open && (
        <div className="card absolute right-0 top-11 z-40 w-80 max-w-[90vw] shadow-xl">
          <div className="flex items-center justify-between border-b border-line px-3 py-2"><b className="text-sm">Notifications</b><button className="text-xs text-accent" onClick={async () => { await api.post("/api/notifications/read-all"); qc.invalidateQueries({ queryKey: ["notifications"] }); }}>Mark all read</button></div>
          <div className="max-h-80 overflow-y-auto">
            {q.data?.items?.length ? q.data.items.map((n: any) => (
              <div key={n.id} className={clsx("border-b border-line/60 px-3 py-2 text-sm", !n.is_read && "bg-accent/5")}><div className="flex items-center gap-2"><Dot level={n.level === "critical" ? "Critical" : n.level === "warning" ? "Moderate" : "Low"} /><span className="font-medium">{n.title}</span></div><p className="mt-0.5 text-xs text-muted">{ago(n.created_at)}</p></div>
            )) : <p className="p-4 text-center text-sm text-muted">No notifications</p>}
          </div>
          <button className="w-full px-3 py-2 text-center text-xs text-accent" onClick={() => { setOpen(false); nav("/notifications"); }}>View all</button>
        </div>
      )}
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth(); const { theme, toggle } = useTheme(); const { connected } = useLive(); const [drawer, setDrawer] = useState(false);
  const crumbs = useCrumbs(); const loc = useLocation();
  useEffect(() => setDrawer(false), [loc.pathname]);
  const items = useMemo(() => NAV.filter((n) => !n.roles || n.roles.includes(user!.role)), [user]);
  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Main">
      <Link to="/" className="flex items-center gap-2 px-4 py-4"><div className="grid h-8 w-8 place-items-center rounded-lg bg-accent/15 text-accent"><ShieldAlert size={18} /></div><div><div className="text-sm font-bold tracking-wide">INDUSTRIX <span className="text-accent">AI</span></div><div className="text-[10px] uppercase tracking-widest text-muted">Risk Intelligence</div></div></Link>
      <div className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-3">
        {items.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => clsx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition", isActive ? "bg-accent/12 font-medium text-accent" : "text-muted hover:bg-surface2 hover:text-ink")}>
            <n.icon size={17} />{n.label}
          </NavLink>
        ))}
      </div>
      <div className="border-t border-line p-3 text-xs text-muted"><div className="font-medium text-ink">{user!.full_name}</div><div>{title(user!.role)}</div></div>
    </nav>
  );
  return (
    <div className="flex h-full">
      <aside className="hidden w-60 shrink-0 border-r border-line bg-surface/80 lg:block">{sidebar}</aside>
      {drawer && <div className="fixed inset-0 z-50 flex lg:hidden"><div className="w-64 border-r border-line bg-surface">{sidebar}</div><div className="flex-1 bg-black/50" onClick={() => setDrawer(false)} /></div>}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-surface/70 px-3 py-2.5 backdrop-blur sm:px-5">
          <button className="btn-ghost px-2.5 lg:hidden" aria-label="Open menu" onClick={() => setDrawer(!drawer)}>{drawer ? <X size={16} /> : <Menu size={16} />}</button>
          <SearchBox />
          <div className="ml-auto flex items-center gap-2">
            <span className={clsx("hidden items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs sm:flex", connected ? "border-ok/40 text-ok" : "border-warn/40 text-warn")} title="WebSocket live feed"><span className={clsx("h-1.5 w-1.5 rounded-full", connected ? "bg-ok" : "bg-warn")} />{connected ? "Live" : "Reconnecting"}</span>
            <Badge color="accent" className="hidden md:inline-flex">SIMULATED DATA</Badge>
            <button className="btn-ghost px-2.5" aria-label="Toggle theme" onClick={toggle}>{theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}</button>
            <Bell_ />
            <button className="btn-ghost px-2.5" aria-label="Sign out" title="Sign out" onClick={logout}><LogOut size={16} /></button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto px-3 py-5 sm:px-6">
          <nav aria-label="Breadcrumb" className="mb-3 flex items-center gap-1 text-xs text-muted">{crumbs.map((c, i) => <span key={c.to} className="flex items-center gap-1">{i > 0 && <ChevronRight size={12} />}{i === crumbs.length - 1 ? <span className="text-ink">{c.label}</span> : <Link to={c.to} className="hover:text-accent">{c.label}</Link>}</span>)}</nav>
          <Outlet />
          <p className="mt-10 border-t border-line pt-4 text-center text-[11px] text-muted">INDUSTRIX AI is a decision-support prototype, not a certified industrial safety controller. It never replaces emergency services, certified safety officers or official evacuation procedures.</p>
        </main>
      </div>
    </div>
  );
}
