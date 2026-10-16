export const getBusiness = () => localStorage.getItem("cf_business") ?? "";
export const setBusiness = (id: string) => localStorage.setItem("cf_business", id);

export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (getBusiness()) headers["X-Business-Id"] = getBusiness();
  const r = await fetch(path, { credentials: "same-origin", ...opts, headers: { ...headers, ...(opts.headers as Record<string, string> | undefined) } });
  if (r.status === 401 && !path.startsWith("/api/auth/")) window.dispatchEvent(new Event("auth-required"));
  if (!r.ok) {
    const t = await r.text();
    let msg = t; try { msg = JSON.parse(t).detail ?? t; } catch { /* plain text */ }
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return r.json();
}
export const post = (p: string, body?: unknown) => api(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
export const put = (p: string, body: unknown) => api(p, { method: "PUT", body: JSON.stringify(body) });
export const del = (p: string) => api(p, { method: "DELETE" });
