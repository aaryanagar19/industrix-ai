import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, tokenStore } from "../services/api";

type Ctx = { theme: "dark" | "light"; setTheme: (t: "dark" | "light") => void; toggle: () => void };
const ThemeCtx = createContext<Ctx>(null as any);
export const useTheme = () => useContext(ThemeCtx);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setT] = useState<"dark" | "light">((localStorage.getItem("ix_theme") as any) || "dark");
  useEffect(() => { document.documentElement.classList.toggle("dark", theme === "dark"); localStorage.setItem("ix_theme", theme); }, [theme]);
  const setTheme = (t: "dark" | "light") => { setT(t); if (tokenStore.get()) api.patch("/api/auth/me/preferences", { theme: t }).catch(() => {}); };
  return <ThemeCtx.Provider value={{ theme, setTheme, toggle: () => setTheme(theme === "dark" ? "light" : "dark") }}>{children}</ThemeCtx.Provider>;
}
