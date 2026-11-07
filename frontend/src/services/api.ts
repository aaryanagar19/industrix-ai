const BASE = (import.meta as any).env?.VITE_API_URL || "";
export const tokenStore = {
  get: () => localStorage.getItem("ix_token"),
  set: (t: string) => localStorage.setItem("ix_token", t),
  clear: () => localStorage.removeItem("ix_token"),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

function msg(detail: any): string {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return JSON.stringify(detail);
}

async function raw(method: string, path: string, body?: unknown, form?: FormData): Promise<Response> {
  const headers: Record<string, string> = {};
  const t = tokenStore.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(BASE + path, { method, headers, body: form ?? (body !== undefined ? JSON.stringify(body) : undefined) });
  if (res.status === 401 && !path.includes("/auth/login")) { tokenStore.clear(); window.dispatchEvent(new Event("ix-unauth")); }
  if (!res.ok) {
    let d: any = null;
    try { d = (await res.json()).detail; } catch { /* ignore */ }
    throw new ApiError(res.status, msg(d) || res.statusText);
  }
  return res;
}

export function qs(params?: Record<string, any>) {
  if (!params) return "";
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== "") u.set(k, String(v)); });
  const s = u.toString();
  return s ? `?${s}` : "";
}

const json = async (m: string, p: string, b?: unknown) => (await raw(m, p, b)).json();
export const api = {
  get: (p: string, params?: Record<string, any>) => json("GET", p + qs(params)),
  post: (p: string, b?: unknown) => json("POST", p, b ?? {}),
  patch: (p: string, b?: unknown) => json("PATCH", p, b ?? {}),
  put: (p: string, b?: unknown) => json("PUT", p, b ?? {}),
  del: async (p: string) => { await raw("DELETE", p); },
  upload: async (p: string, form: FormData) => (await raw("POST", p, undefined, form)).json(),
  blob: async (p: string) => (await raw("GET", p)).blob(),
};

export async function download(path: string, filename: string) {
  const blob = await api.blob(path);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function wsUrl(token: string) {
  const base = BASE || window.location.origin;
  return base.replace(/^http/, "ws") + `/ws/live?token=${encodeURIComponent(token)}`;
}
