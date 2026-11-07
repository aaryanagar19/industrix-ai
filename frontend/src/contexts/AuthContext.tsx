import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import { api, tokenStore } from "../services/api";

export type User = { id: number; email: string; full_name: string; role: string; preferences: Record<string, any> };
type Ctx = { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; register: (e: string, p: string, n: string) => Promise<void>; logout: () => void; refresh: () => Promise<void>; can: (...roles: string[]) => boolean };
const AuthCtx = createContext<Ctx>(null as any);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());
  const refresh = useCallback(async () => { try { setUser(await api.get("/api/auth/me")); } catch { tokenStore.clear(); setUser(null); } finally { setLoading(false); } }, []);
  useEffect(() => { if (tokenStore.get()) refresh(); }, [refresh]);
  useEffect(() => { const f = () => setUser(null); window.addEventListener("ix-unauth", f); return () => window.removeEventListener("ix-unauth", f); }, []);
  const accept = (r: any) => { tokenStore.set(r.access_token); setUser(r.user); };
  const value: Ctx = {
    user, loading, refresh,
    login: async (email, password) => accept(await api.post("/api/auth/login", { email, password })),
    register: async (email, password, full_name) => accept(await api.post("/api/auth/register", { email, password, full_name })),
    logout: () => { tokenStore.clear(); setUser(null); },
    can: (...roles) => !!user && (user.role === "super_admin" || roles.includes(user.role)),
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
