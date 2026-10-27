import axios, { AxiosError } from "axios";
import { toast } from "sonner";

/**
 * Client HTTP de l'application.
 * - Base relative (/api) : le proxy de développement (Vite) ou le reverse
 *   proxy de production (nginx) route le trafic — jamais d'URL codée en dur.
 * - Jeton JWT en en-tête Authorization, rafraîchi une fois sur 401.
 */
export const api = axios.create({ baseURL: "/api" });

const TOKEN_KEY = "pbs.access";
const REFRESH_KEY = "pbs.refresh";

export function storeTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY);
}

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshToken(): Promise<string | null> {
  if (!refreshing) {
    const refresh = localStorage.getItem(REFRESH_KEY);
    if (!refresh) return null;
    refreshing = axios
      .post("/api/auth/refresh/", { refresh })
      .then((res) => {
        const access = res.data.access as string;
        localStorage.setItem(TOKEN_KEY, access);
        return access;
      })
      .catch(() => {
        clearTokens();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const original = error.config as
      | { _retry?: boolean; url?: string; headers?: Record<string, string> }
      | undefined;
    if (error.response?.status === 401 && original && !original._retry && !original.url?.includes("auth/")) {
      original._retry = true;
      const token = await refreshToken();
      if (token) {
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${token}` };
        return api({ ...original, headers: original.headers as any });
      }
      window.location.href = "/connexion";
    }
    return Promise.reject(error);
  }
);

export function detailErreur(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string } | undefined;
    return data?.detail || `Erreur réseau (${error.response?.status ?? "indisponible"})`;
  }
  return "Erreur inattendue";
}

export function notifierErreur(error: unknown, message?: unknown) {
  toast.error(typeof message === "string" && message ? message : detailErreur(error));
}

/** Liste générique (pagination DRF). */
export interface Liste<T> {
  count: number;
  results: T[];
}

export async function fetchListe<T>(url: string, params?: Record<string, string | number | undefined>) {
  const res = await api.get<Liste<T>>(url, { params });
  return res.data;
}
