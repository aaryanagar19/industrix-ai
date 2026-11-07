import { FormEvent, useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";
import { Button, Field, Input } from "../components/ui";

const DEMO = [["Super Admin", "admin@industrix.dev", "Admin@12345"], ["Safety Manager", "safety.manager@industrix.dev", "SafetyMgr@123"], ["Plant Manager", "plant.manager@industrix.dev", "PlantMgr@123"], ["Maintenance Engineer", "engineer@industrix.dev", "Engineer@123"], ["Safety Officer", "officer@industrix.dev", "Officer@123"]];

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [name, setName] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr("");
    if (mode === "register" && name.trim().length < 2) return setErr("Please enter your full name");
    if (password.length < (mode === "register" ? 8 : 1)) return setErr(mode === "register" ? "Password must be at least 8 characters" : "Enter your password");
    setBusy(true);
    try { mode === "login" ? await login(email, password) : await register(email, password, name); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="grid min-h-full place-items-center p-4">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid w-full max-w-4xl overflow-hidden rounded-2xl border border-line bg-surface md:grid-cols-2">
        <div className="hidden flex-col justify-between bg-gradient-to-br from-accent/20 via-surface2 to-surface p-8 md:flex">
          <div className="flex items-center gap-2"><div className="grid h-10 w-10 place-items-center rounded-xl bg-accent/20 text-accent"><ShieldAlert /></div><div className="font-bold tracking-wide">INDUSTRIX <span className="text-accent">AI</span></div></div>
          <div><h2 className="text-2xl font-semibold leading-snug">Predict industrial hazards before they become incidents.</h2><p className="mt-3 text-sm text-muted">XGBoost risk scoring, LSTM forecasting, Isolation-Forest anomaly detection and SHAP explanations — on one command centre.</p></div>
          <p className="text-xs text-muted">Decision-support prototype. Demo runs on simulated sensor data.</p>
        </div>
        <form onSubmit={submit} className="space-y-4 p-6 sm:p-8" noValidate>
          <h1 className="text-xl font-semibold">{mode === "login" ? "Sign in" : "Create account"}</h1>
          {mode === "register" && <Field label="Full name"><Input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></Field>}
          <Field label="Email"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required /></Field>
          <Field label="Password" hint={mode === "register" ? "At least 8 characters. New accounts get the Plant Manager role; an admin can change it." : undefined}><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} required /></Field>
          {err && <p role="alert" className="text-sm text-danger">{err}</p>}
          <Button type="submit" className="w-full" loading={busy}>{mode === "login" ? "Sign in" : "Register"}</Button>
          <button type="button" className="w-full text-center text-sm text-accent" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>{mode === "login" ? "No account? Register" : "Have an account? Sign in"}</button>
          {mode === "login" && (
            <div className="rounded-lg border border-line bg-surface2/50 p-3"><p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">Development demo accounts (click to fill)</p>
              <div className="flex flex-wrap gap-1.5">{DEMO.map(([r, e, p]) => <button type="button" key={e} className="rounded-full border border-line px-2.5 py-1 text-xs hover:border-accent hover:text-accent" onClick={() => { setEmail(e); setPassword(p); }}>{r}</button>)}</div></div>
          )}
        </form>
      </motion.div>
    </div>
  );
}
