import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { tokenStore, wsUrl } from "../services/api";
import { useAuth } from "./AuthContext";
import { useToast } from "../components/ui";

export type Reading = { machine_id: number; machine_code: string; timestamp: string; temperature: number; vibration: number; pressure: number; load_pct: number; data_source: string };
export type FeedItem = { id: string; kind: string; level: string; text: string; time: string };
type Ctx = { connected: boolean; readings: Record<number, Reading>; history: Record<number, Reading[]>; predictions: Record<number, any>; feed: FeedItem[]; messageCount: number };
const LiveCtx = createContext<Ctx>({ connected: false, readings: {}, history: {}, predictions: {}, feed: [], messageCount: 0 });
export const useLive = () => useContext(LiveCtx);

export function LiveProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const toast = useToast();
  const qc = useQueryClient();
  const [state, setState] = useState<Ctx>({ connected: false, readings: {}, history: {}, predictions: {}, feed: [], messageCount: 0 });
  const buf = useRef<any[]>([]);

  useEffect(() => {
    if (!user) return;
    let ws: WebSocket | null = null, stop = false, retry = 0, ping: any;
    const connect = () => {
      const t = tokenStore.get(); if (!t) return;
      ws = new WebSocket(wsUrl(t));
      ws.onopen = () => { retry = 0; setState((s) => ({ ...s, connected: true })); ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000); };
      ws.onmessage = (e) => { try { buf.current.push(JSON.parse(e.data)); } catch { /* ignore */ } };
      ws.onclose = () => { clearInterval(ping); setState((s) => ({ ...s, connected: false })); if (!stop) setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000)); };
    };
    connect();
    const flush = setInterval(() => {
      const msgs = buf.current.splice(0);
      if (!msgs.length) return;
      let notified = false;
      const toasts: [string, string][] = [];
      setState((s) => {
        const readings = { ...s.readings }, history = { ...s.history }, predictions = { ...s.predictions }; let feed = s.feed;
        for (const m of msgs) {
          if (m.type === "reading") { const r = m.data; readings[r.machine_id] = r; history[r.machine_id] = [...(history[r.machine_id] || []).slice(-179), r]; }
          else if (m.type === "prediction") predictions[m.data.machine_id] = m.data;
          else if (m.type === "anomaly") feed = [{ id: `a${m.data.id}`, kind: "anomaly", level: m.data.severity === "critical" ? "critical" : "warning", text: `${m.data.machine_code}: ${m.data.parameter} ${Number(m.data.observed_value).toFixed(1)}${m.data.unit} outside ${m.data.expected_low}–${m.data.expected_high}`, time: m.data.timestamp }, ...feed].slice(0, 60);
          else if (m.type === "notification") { notified = true; feed = [{ id: `n${m.data.id}`, kind: "notification", level: m.data.level, text: m.data.title, time: m.data.created_at }, ...feed].slice(0, 60); toasts.push([m.data.title, m.data.level === "critical" ? "error" : "warning"]); }
        }
        return { ...s, readings, history, predictions, feed, messageCount: s.messageCount + msgs.length };
      });
      toasts.slice(0, 2).forEach(([t, k]) => toast(t, k as any));
      if (notified) qc.invalidateQueries({ queryKey: ["notifications"] });
    }, 700);
    return () => { stop = true; clearInterval(flush); clearInterval(ping); ws?.close(); };
  }, [user?.id]);
  return <LiveCtx.Provider value={state}>{children}</LiveCtx.Provider>;
}
