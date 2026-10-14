export async function api<T = any>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
export const post = (p: string, body?: unknown) => api(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
