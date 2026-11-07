import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Inbox, X, XCircle } from "lucide-react";
import { RISK_COLOR, SEV_COLOR, title } from "../utils/format";

// ---------- toasts ----------
type ToastKind = "success" | "error" | "warning" | "info";
const ToastCtx = createContext<(m: string, k?: ToastKind) => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; m: string; k: ToastKind }[]>([]);
  const push = useCallback((m: string, k: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s.slice(-3), { id, m, k }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), 5000);
  }, []);
  const icon = { success: <CheckCircle2 size={16} className="text-ok" />, error: <XCircle size={16} className="text-danger" />, warning: <AlertTriangle size={16} className="text-warn" />, info: <Info size={16} className="text-accent" /> };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 max-w-[90vw] flex-col gap-2" role="status" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => (
            <motion.div key={t.id} initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 40 }} className="card pointer-events-auto flex items-start gap-2 p-3 text-sm shadow-lg">
              {icon[t.k]}<span className="flex-1">{t.m}</span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}

// ---------- basics ----------
export const Card = ({ children, className, ...p }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) => <div className={clsx("card", className)} {...p}>{children}</div>;
export const CardHeader = ({ title: t, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) => (
  <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
    <div><h3 className="text-sm font-semibold">{t}</h3>{sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}</div>{right}
  </div>
);
export function PageHeader({ title: t, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{t}</h1>{sub && <p className="mt-1 max-w-3xl text-sm text-muted">{sub}</p>}</div>
      <div className="flex flex-wrap items-center gap-2">{actions}</div>
    </div>
  );
}
export const Skeleton = ({ className }: { className?: string }) => <div className={clsx("skeleton", className)} aria-hidden />;
export const Empty = ({ text = "No data yet", hint }: { text?: string; hint?: string }) => (
  <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-center text-muted"><Inbox size={28} /><p className="text-sm font-medium text-ink">{text}</p>{hint && <p className="max-w-sm text-xs">{hint}</p>}</div>
);
export const ErrorState = ({ error, retry }: { error: unknown; retry?: () => void }) => (
  <div className="flex flex-col items-center gap-2 px-4 py-8 text-center"><XCircle className="text-danger" size={26} /><p className="text-sm">{(error as Error)?.message || "Something went wrong"}</p>{retry && <button className="btn-ghost" onClick={retry}>Retry</button>}</div>
);
export function Async({ q, children, skeleton }: { q: { isLoading: boolean; error: unknown; data: any; refetch: () => void }; children: (d: any) => ReactNode; skeleton?: ReactNode }) {
  if (q.isLoading) return <>{skeleton ?? <div className="space-y-2 p-4"><Skeleton className="h-6 w-1/3" /><Skeleton className="h-40 w-full" /></div>}</>;
  if (q.error) return <ErrorState error={q.error} retry={q.refetch} />;
  return <>{children(q.data)}</>;
}

export function Badge({ children, color = "muted", className }: { children: ReactNode; color?: "ok" | "warn" | "orange" | "danger" | "accent" | "muted"; className?: string }) {
  const map: Record<string, string> = { ok: "bg-ok/15 text-ok", warn: "bg-warn/15 text-warn", orange: "bg-orange/15 text-orange", danger: "bg-danger/15 text-danger", accent: "bg-accent/15 text-accent", muted: "bg-surface2 text-muted" };
  return <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", map[color], className)}>{children}</span>;
}
const catColor: Record<string, any> = { Low: "ok", Moderate: "warn", High: "orange", Critical: "danger", low: "ok", medium: "warn", high: "orange", critical: "danger" };
export const RiskBadge = ({ level }: { level?: string | null }) => (level ? <Badge color={catColor[level] || "muted"}>{title(level)}</Badge> : <Badge>n/a</Badge>);
export const StatusBadge = ({ s }: { s: string }) => {
  const c: Record<string, any> = { running: "ok", idle: "muted", maintenance: "warn", offline: "danger", open: "danger", responding: "warn", resolved: "ok", closed: "muted", scheduled: "accent", in_progress: "warn", completed: "ok", cancelled: "muted", done: "ok", pending: "warn", skipped: "muted" };
  return <Badge color={c[s] || "muted"}>{title(s)}</Badge>;
};

export function Stat({ label, value, sub, tone, icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "ok" | "warn" | "orange" | "danger" | "accent"; icon?: ReactNode }) {
  const t = tone ? { ok: "text-ok", warn: "text-warn", orange: "text-orange", danger: "text-danger", accent: "text-accent" }[tone] : "";
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted"><span>{label}</span>{icon}</div>
      <div className={clsx("mt-2 text-2xl font-semibold tabular-nums", t)}>{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </Card>
  );
}

export const Button = ({ variant = "primary", className, loading, children, ...p }: { variant?: "primary" | "ghost" | "danger"; loading?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) => (
  <button className={clsx(variant === "primary" ? "btn-primary" : variant === "danger" ? "btn-danger" : "btn-ghost", className)} disabled={loading || p.disabled} {...p}>{loading && <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />}{children}</button>
);

export const Field = ({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) => (
  <label className="block"><span className="label">{label}</span>{children}{hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}</label>
);
export const Select = ({ className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) => <select className={clsx("input", className)} {...p}>{children}</select>;
export const Input = ({ className, ...p }: React.InputHTMLAttributes<HTMLInputElement>) => <input className={clsx("input", className)} {...p} />;

export function Modal({ open, onClose, title: t, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => { if (!open) return; const f = (e: KeyboardEvent) => e.key === "Escape" && onClose(); window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [open, onClose]);
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={onClose}>
          <motion.div role="dialog" aria-modal="true" aria-label={t} initial={{ y: 16, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 16, opacity: 0 }} onMouseDown={(e) => e.stopPropagation()}
            className={clsx("card max-h-[90vh] w-full overflow-y-auto p-5", wide ? "max-w-2xl" : "max-w-md")}>
            <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">{t}</h2><button aria-label="Close" onClick={onClose} className="rounded p-1 text-muted hover:bg-surface2"><X size={18} /></button></div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Confirm({ open, title: t, message, confirmLabel = "Confirm", danger, onConfirm, onClose }: { open: boolean; title: string; message: ReactNode; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} onClose={onClose} title={t}>
      <div className="text-sm text-muted">{message}</div>
      <div className="mt-5 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant={danger ? "danger" : "primary"} onClick={() => { onConfirm(); onClose(); }}>{confirmLabel}</Button></div>
    </Modal>
  );
}

export const Table = ({ children }: { children: ReactNode }) => <div className="overflow-x-auto"><table className="w-full min-w-[640px] border-collapse">{children}</table></div>;
export const Tabs = ({ tabs, value, onChange }: { tabs: { id: string; label: string }[]; value: string; onChange: (v: string) => void }) => (
  <div className="mb-4 flex gap-1 overflow-x-auto rounded-lg border border-line bg-surface2/50 p-1" role="tablist">
    {tabs.map((t) => <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)} className={clsx("whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition", value === t.id ? "bg-surface text-accent shadow-sm" : "text-muted hover:text-ink")}>{t.label}</button>)}
  </div>
);
export const Disclaimer = ({ children }: { children: ReactNode }) => <div className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-ink"><AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" /><div>{children}</div></div>;
export const SimBanner = () => <Disclaimer><b>Simulated data.</b> Readings come from the built-in industrial simulator. No physical industrial hardware is connected.</Disclaimer>;
export const Pager = ({ page, total, size, onPage }: { page: number; total: number; size: number; onPage: (p: number) => void }) => {
  const pages = Math.max(Math.ceil(total / size), 1);
  return <div className="flex items-center justify-between border-t border-line px-4 py-2 text-xs text-muted"><span>{total} records</span><div className="flex items-center gap-2"><button className="btn-ghost px-2 py-1" disabled={page <= 1} onClick={() => onPage(page - 1)}>Prev</button><span>{page} / {pages}</span><button className="btn-ghost px-2 py-1" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</button></div></div>;
};
export const Dot = ({ level }: { level?: string }) => <span className="inline-block h-2 w-2 rounded-full" style={{ background: RISK_COLOR[level || ""] || SEV_COLOR[level || ""] || "rgb(var(--muted))" }} />;
