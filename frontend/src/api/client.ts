import { getCurrentUserForApi } from "../auth/useAuth";
import { emitToast } from "../components/Toast";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

let toastedUnauthorized = false;

async function authHeader(): Promise<Record<string, string>> {
  const user = getCurrentUserForApi();
  if (!user) return {};
  try {
    const token = await user.getIdToken();
    return { Authorization: `Bearer ${token}` };
  } catch {
    return {};
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {
    ...(await authHeader()),
    ...(body ? { "Content-Type": "application/json" } : {}),
  };
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    // Token expired or missing — push the user back to login. The Firebase SDK
    // refreshes tokens transparently, so 401s usually mean a real sign-out.
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      // Toast once per page-load so the user understands why they were
      // bounced. Without this the redirect feels like a random tab close.
      if (!toastedUnauthorized) {
        toastedUnauthorized = true;
        emitToast({
          kind: "error",
          message: "Your session expired. Please sign in again.",
        });
      }
      const here = window.location.pathname + window.location.search;
      window.location.assign(`/login?next=${encodeURIComponent(here)}`);
    }
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${method} ${path} failed: ${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body: unknown) => request<T>("POST", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
  put: <T,>(path: string, body: unknown) => request<T>("PUT", path, body),
  del: (path: string) => request<void>("DELETE", path),
};
