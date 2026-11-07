import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { api } from "../services/api";

export function useGet<T = any>(path: string, params?: Record<string, any>, opts: { refetchMs?: number; enabled?: boolean } = {}) {
  return useQuery<T>({ queryKey: [path, params], queryFn: () => api.get(path, params), refetchInterval: opts.refetchMs, enabled: opts.enabled ?? true, placeholderData: keepPreviousData });
}
export const useMachines = () => useGet<any>("/api/machines", { page_size: 200 });
export const useFacilities = () => useGet<any[]>("/api/facilities");
