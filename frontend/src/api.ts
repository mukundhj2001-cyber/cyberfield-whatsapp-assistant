export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 401 && !path.startsWith("/api/auth/")) window.dispatchEvent(new Event("auth-required"));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export const post = (p: string, body?: unknown) => api(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
