import type { ApiOptions, Capabilities, Effect, Job, Presets, ServerSettings } from "./vui-types";

const FALLBACK_API = "http://localhost:8000";
export const API_URL_KEY = "vui-api-url";
export const HISTORY_KEY = "vui-job-history";
export const THEME_KEY = "vui-theme";

export function getApiUrl() {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem(API_URL_KEY);
    if (stored) return stored.replace(/\/$/, "");
  }
  return (import.meta.env['VITE_API_URL'] || FALLBACK_API).replace(/\/$/, "");
}

async function apiError(response: Response) {
  let message = `Ошибка API (${response.status})`;
  try {
    const body = await response.json() as { detail?: string; message?: string };
    message = body.detail || body.message || message;
  } catch {
    const text = await response.text().catch(() => "");
    if (text) message = text;
  }
  return new Error(message);
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiUrl()}${path}`, init);
  if (!response.ok) throw await apiError(response);
  return response.json() as Promise<T>;
}

export async function apiBlob(path: string, init?: RequestInit) {
  const response = await fetch(`${getApiUrl()}${path}`, init);
  if (!response.ok) throw await apiError(response);
  return response.blob();
}

export function createMultipart(params: unknown, fields: Record<string, File | File[] | undefined>) {
  const body = new FormData();
  body.append("params", JSON.stringify(params));
  Object.entries(fields).forEach(([key, value]) => {
    if (Array.isArray(value)) value.forEach((file) => body.append(key, file));
    else if (value) body.append(key, value);
  });
  return body;
}

export const getHealth = () => apiFetch<{ status: string }>("/api/health");
export const getCapabilities = () => apiFetch<Capabilities>("/api/capabilities");
export const getOptions = () => apiFetch<ApiOptions>("/api/options");
export const getEffects = () => apiFetch<{ effects: Effect[] }>("/api/effects");
export const getPresets = () => apiFetch<Presets>("/api/presets");
export const getSettings = () => apiFetch<ServerSettings>("/api/settings");
export const putSettings = (data: ServerSettings) => apiFetch<ServerSettings>("/api/settings", {
  method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data }),
});
export const getJob = (id: string) => apiFetch<Job>(`/api/jobs/${id}`);
export const cancelJob = (id: string) => apiFetch<Job>(`/api/jobs/${id}/cancel`, { method: "POST" });