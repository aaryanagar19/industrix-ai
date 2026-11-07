import { useGet } from "../hooks/useApi";
import { Select } from "./ui";

export default function MachinePicker({ value, onChange, className, allowAll }: { value: string; onChange: (v: string) => void; className?: string; allowAll?: boolean }) {
  const q = useGet<any>("/api/machines", { page_size: 200 });
  return (
    <Select aria-label="Machine" value={value} onChange={(e) => onChange(e.target.value)} className={className ?? "w-56"}>
      {allowAll ? <option value="">All machines</option> : <option value="" disabled>Select machine…</option>}
      {(q.data?.items || []).map((m: any) => <option key={m.id} value={m.id}>{m.code} — {m.name}</option>)}
    </Select>
  );
}
