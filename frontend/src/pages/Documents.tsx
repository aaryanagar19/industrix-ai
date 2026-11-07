import { useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, FileUp } from "lucide-react";
import { Async, Badge, Button, Card, CardHeader, Disclaimer, Empty, Field, Input, PageHeader, Pager, RiskBadge, Select, Tabs, useToast } from "../components/ui";
import { useGet } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { api, download } from "../services/api";
import { title, when } from "../utils/format";

const TYPES = ["maintenance_log", "inspection_report", "incident_description", "near_miss_report", "equipment_complaint"];
const chip = (xs: string[], c: any = "muted") => xs.length ? <div className="flex flex-wrap gap-1.5">{xs.map((x) => <Badge key={x} color={c}>{x}</Badge>)}</div> : <span className="text-muted">none detected</span>;

export default function Documents() {
  const { can } = useAuth(); const toast = useToast(); const qc = useQueryClient(); const [sp, setSp] = useSearchParams(); const sel = sp.get("id");
  const [mode, setMode] = useState("upload"); const [dt, setDt] = useState(TYPES[0]); const [txt, setTxt] = useState(""); const [name, setName] = useState(""); const [page, setPage] = useState(1); const file = useRef<HTMLInputElement>(null);
  const list = useGet<any>("/api/documents", { page, page_size: 10 }, { refetchMs: 30000 });
  const an = useGet<any>(`/api/documents/${sel}/analysis`, undefined, { enabled: !!sel });
  const done = (r: any) => { toast("Document analysed", "success"); qc.invalidateQueries({ queryKey: ["/api/documents"] }); setSp({ id: String(r.id) }); setTxt(""); setName(""); if (file.current) file.current.value = ""; };
  const up = useMutation({ mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); fd.append("doc_type", dt); return api.upload("/api/documents/upload", fd); }, onSuccess: done, onError: (e: any) => toast(e.message, "error") });
  const tx = useMutation({ mutationFn: () => api.post("/api/documents/text", { title: name, doc_type: dt, text: txt }), onSuccess: done, onError: (e: any) => toast(e.message, "error") });
  const canWrite = can("safety_manager", "safety_officer", "maintenance_engineer", "plant_manager");
  const onFile = () => { const f = file.current?.files?.[0]; if (!f) return toast("Choose a file first", "warning"); if (f.size > 5 * 1024 * 1024) return toast("File exceeds 5 MB", "error"); up.mutate(f); };
  return (
    <>
      <PageHeader title="Document Intelligence" sub="NLP analysis of maintenance logs, inspection reports and incident descriptions: entities, hazards, issues, urgency and follow-up actions. Works offline with a TF-IDF classifier and rule-based extraction." />
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          {canWrite && <Card className="p-4"><Tabs value={mode} onChange={setMode} tabs={[{ id: "upload", label: "Upload file" }, { id: "text", label: "Enter text" }]} />
            <div className="space-y-3"><Field label="Document type"><Select value={dt} onChange={(e) => setDt(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{title(t)}</option>)}</Select></Field>
              {mode === "upload" ? <><Field label="File (.txt .md .log .csv .pdf, max 5 MB)"><input ref={file} type="file" accept=".txt,.md,.log,.csv,.pdf" className="input" /></Field><Button onClick={onFile} loading={up.isPending}><FileUp size={15} />Upload & analyse</Button></>
                : <><Field label="Title"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field><Field label="Text"><textarea className="input min-h-[140px]" value={txt} onChange={(e) => setTxt(e.target.value)} placeholder="Paste a maintenance note, inspection report or incident description…" /></Field>
                  <Button loading={tx.isPending} onClick={() => name.trim().length < 2 ? toast("Enter a title", "warning") : txt.trim().length < 10 ? toast("Text must be at least 10 characters", "warning") : tx.mutate()}>Analyse text</Button></>}</div></Card>}
          <Card><CardHeader title="Documents" />{list.data?.items?.length ? <><div className="divide-y divide-line/60">{list.data.items.map((d: any) => <button key={d.id} onClick={() => setSp({ id: String(d.id) })} className={`block w-full px-4 py-2.5 text-left hover:bg-surface2 ${String(d.id) === sel ? "bg-accent/10" : ""}`}><div className="flex items-center justify-between text-sm"><b className="truncate">{d.filename}</b>{d.urgency && <RiskBadge level={d.urgency} />}</div><p className="text-xs text-muted">{title(d.doc_type)} · {when(d.uploaded_at)}</p></button>)}</div><Pager page={page} total={list.data.total} size={10} onPage={setPage} /></> : <Empty text="No documents yet" />}</Card>
        </div>
        <Card>{sel ? <Async q={an}>{(d) => { const a = d.analysis; return (<><CardHeader title={`NLP analysis report — ${d.document.filename}`} sub={`${title(d.document.doc_type)} · ${a.model_version}`} right={<Button variant="ghost" onClick={() => download(`/api/documents/${sel}/report`, `nlp_analysis_${sel}.pdf`).catch((e) => toast(e.message, "error"))}><Download size={14} />PDF</Button>} />
          <div className="space-y-4 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-4"><div><p className="label">Incident type</p><Badge color="accent">{title(a.incident_type)}</Badge> <span className="text-xs text-muted">{a.classification_method}, confidence {a.classifier_confidence}</span></div><div><p className="label">Urgency</p><RiskBadge level={a.urgency} /></div></div>
            <div><p className="label">Summary</p><p>{a.summary}</p>{a.llm_summary && <p className="mt-1 text-muted">LLM: {a.llm_summary}</p>}</div>
            <div className="grid gap-4 sm:grid-cols-2"><div><p className="label">Equipment</p>{chip([...a.machines.codes, ...a.machines.names], "accent")}</div><div><p className="label">Hazards</p>{chip(a.hazards, "danger")}</div><div><p className="label">Maintenance issues / faults</p>{chip(a.issues, "warn")}</div><div><p className="label">Measurements</p>{chip(a.measurements)}</div><div><p className="label">Urgency indicators</p>{chip(a.urgency_indicators, "orange")}</div><div><p className="label">Keywords</p>{chip(a.keywords)}</div></div>
            <div><p className="label">Required follow-up actions (extracted sentences)</p>{a.follow_up_actions.length ? <ul className="list-disc space-y-1 pl-5">{a.follow_up_actions.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul> : <span className="text-muted">none detected</span>}</div>
            <details><summary className="cursor-pointer text-xs text-accent">Show source text</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-surface2 p-3 text-xs">{d.text}</pre></details>
            <Disclaimer>{a.disclaimer}</Disclaimer></div></>); }}</Async> : <Empty text="Select or upload a document" hint="The analysis report appears here." />}</Card>
      </div>
    </>
  );
}
