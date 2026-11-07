import { RISK_COLOR, pct } from "../utils/format";

type Props = { data: any; mode: "twin" | "propagation"; selected: number | null; onSelect: (id: number) => void; showEdges: boolean };

export default function PlantMap({ data, mode, selected, onSelect, showEdges }: Props) {
  const nodes: any[] = data.nodes, byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const risk = (n: any) => (mode === "propagation" ? n.propagated_risk : n.model_probability);
  const cat = (n: any) => (mode === "propagation" ? n.category : n.category);
  return (
    <svg viewBox="0 0 1000 600" className="h-auto w-full rounded-xl border border-line bg-surface2/40" role="img" aria-label={mode === "twin" ? "Facility digital twin" : "Risk propagation map"}>
      <defs>
        <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="rgb(var(--muted))" /></marker>
        <marker id="arrHot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="rgb(var(--orange))" /></marker>
        <pattern id="gridp" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="rgb(var(--line))" strokeWidth="0.4" /></pattern>
      </defs>
      <rect width="1000" height="600" fill="url(#gridp)" opacity="0.6" />
      {(data.departments || []).map((d: any) => d.layout && (
        <g key={d.id}><rect x={d.layout.x} y={d.layout.y} width={d.layout.w} height={d.layout.h} rx="14" fill="rgb(var(--surface))" fillOpacity="0.55" stroke="rgb(var(--line))" strokeDasharray="6 4" />
          <text x={d.layout.x + 12} y={d.layout.y + 20} fontSize="12" fontWeight="600" fill="rgb(var(--muted))" style={{ textTransform: "uppercase", letterSpacing: 1 }}>{d.name}</text></g>
      ))}
      {showEdges && data.edges.map((e: any, i: number) => {
        const s = byId[e.source], t = byId[e.target]; if (!s || !t) return null;
        const hot = mode === "propagation" && e.flow > 0.02;
        const dx = t.x - s.x, dy = t.y - s.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
        return <line key={i} x1={s.x + ux * 38} y1={s.y + uy * 24} x2={t.x - ux * 40} y2={t.y - uy * 26} stroke={hot ? "rgb(var(--orange))" : "rgb(var(--muted))"} strokeOpacity={hot ? 0.9 : 0.45} strokeWidth={mode === "propagation" ? 1 + e.flow * 14 : 1.2} markerEnd={hot ? "url(#arrHot)" : "url(#arr)"}><title>{`${s.code} → ${t.code} (${e.relation}, weight ${e.weight}${mode === "propagation" ? `, flow ${e.flow}` : ""})`}</title></line>;
      })}
      {nodes.map((n) => {
        const c = RISK_COLOR[cat(n)] || "rgb(var(--ok))"; const hot = cat(n) === "High" || cat(n) === "Critical"; const sel = selected === n.id;
        return (
          <g key={n.id} transform={`translate(${n.x},${n.y})`} onClick={() => onSelect(n.id)} style={{ cursor: "pointer" }} tabIndex={0} role="button" aria-label={`${n.code} ${cat(n)} risk ${pct(risk(n))}`} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(n.id)}>
            {hot && <rect x={-36} y={-22} width={72} height={44} rx={10} fill="none" stroke={c} strokeWidth={2} className="animate-pulseRing" style={{ transformBox: "fill-box", transformOrigin: "center" }} />}
            <rect x={-36} y={-22} width={72} height={44} rx={10} fill={c} fillOpacity={0.16} stroke={c} strokeWidth={sel ? 3 : 1.5} />
            <text y={-3} textAnchor="middle" fontSize="12" fontWeight="700" fill="rgb(var(--ink))">{n.code}</text>
            <text y={13} textAnchor="middle" fontSize="11" fill={c}>{pct(risk(n), 0)}</text>
            {n.anomaly_level > 0 && <g><circle cx={32} cy={-18} r={7} fill="rgb(var(--danger))" /><text x={32} y={-14} textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">!</text></g>}
            {mode === "propagation" && n.added_by_propagation > 0.005 && <text y={36} textAnchor="middle" fontSize="10" fill="rgb(var(--orange))">+{pct(n.added_by_propagation, 1)} propagated</text>}
          </g>
        );
      })}
    </svg>
  );
}
