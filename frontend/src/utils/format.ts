export const pct = (v?: number | null, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
export const num = (v?: number | null, d = 1) => (v == null ? "—" : Number(v).toFixed(d));
export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
export const timeOnly = (iso?: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—");
export const ago = (iso?: string | null) => {
  if (!iso) return "—";
  const s = Math.max((Date.now() - new Date(iso).getTime()) / 1000, 0);
  return s < 60 ? `${Math.floor(s)}s ago` : s < 3600 ? `${Math.floor(s / 60)}m ago` : s < 86400 ? `${Math.floor(s / 3600)}h ago` : `${Math.floor(s / 86400)}d ago`;
};
export const title = (s?: string | null) => (s ? s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()) : "—");
export const C = { accent: "rgb(var(--accent))", ok: "rgb(var(--ok))", warn: "rgb(var(--warn))", orange: "rgb(var(--orange))", danger: "rgb(var(--danger))", muted: "rgb(var(--muted))", line: "rgb(var(--line))", ink: "rgb(var(--ink))" };
export const RISK_COLOR: Record<string, string> = { Low: C.ok, Moderate: C.warn, High: C.orange, Critical: C.danger };
export const SEV_COLOR: Record<string, string> = { low: C.ok, medium: C.warn, high: C.orange, critical: C.danger };
export const PARAMS: { key: string; label: string; unit: string }[] = [
  { key: "temperature", label: "Temperature", unit: "°C" }, { key: "vibration", label: "Vibration", unit: "mm/s" },
  { key: "pressure", label: "Pressure", unit: "bar" }, { key: "load_pct", label: "Load", unit: "%" },
];
export const FEATURE_LABEL: Record<string, string> = {
  temperature_dev: "Temperature vs baseline", vibration_dev: "Vibration vs baseline", pressure_dev: "Pressure vs baseline", load_pct: "Machine load", equipment_age_years: "Equipment age",
  maintenance_delay_days: "Maintenance overdue", previous_incidents: "Incidents (90 d)", shift_hours: "Shift duration", production_intensity: "Production intensity", weather_severity: "Weather severity",
  inspection_status: "Inspection result", temperature_trend: "Temperature trend", vibration_trend: "Vibration trend",
};
