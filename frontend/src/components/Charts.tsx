import { ReactNode } from "react";
import { ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { C } from "../utils/format";

export const ChartBox = ({ h = 240, children }: { h?: number; children: ReactNode }) => <div style={{ height: h }} className="w-full"><ResponsiveContainer width="100%" height="100%">{children as any}</ResponsiveContainer></div>;
export const axis = { stroke: C.muted, fontSize: 11, tickLine: false, axisLine: { stroke: C.line } } as const;
export const grid = <CartesianGrid stroke={C.line} strokeDasharray="3 3" vertical={false} />;
export const tip = <Tooltip contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", borderRadius: 8, fontSize: 12, color: "rgb(var(--ink))" }} labelStyle={{ color: "rgb(var(--muted))" }} />;
export const hhmm = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const dd = (iso: string) => new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
export const ddhh = (iso: string) => new Date(iso).toLocaleString([], { day: "numeric", month: "short", hour: "2-digit" });
export { XAxis, YAxis };
