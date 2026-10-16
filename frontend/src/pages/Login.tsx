import { useState } from "react";
import { post } from "../api";

export default function Login({ demo, onDone }: { demo: boolean; onDone: (user: string) => void }) {
  const [u, setU] = useState(""); const [p, setP] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr("");
    try { const r = await post("/api/auth/login", { username: u, password: p }); onDone(r.user); }
    catch { setErr("Wrong username or password."); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={submit} className="card mx-auto max-w-sm p-6 space-y-4 mt-10" data-testid="login">
      <div><h1 className="font-display text-xl font-bold gold-text">Owner login</h1>
        <p className="text-xs text-zinc-400 mt-1">The dashboard holds customer data, so it's behind a login.</p></div>
      <input data-testid="login-user" className="input" placeholder="Username" autoComplete="username" value={u} onChange={(e) => setU(e.target.value)} />
      <input data-testid="login-pass" className="input" type="password" placeholder="Password" autoComplete="current-password" value={p} onChange={(e) => setP(e.target.value)} />
      {err && <div className="text-sm text-red-300">{err}</div>}
      <button data-testid="login-submit" className="btn-gold w-full justify-center" disabled={busy || !u || !p}>Sign in</button>
      {demo && <p className="text-xs text-amber-300/90 border border-amber-500/30 rounded-lg p-2">Demo login: <b>admin</b> / <b>cyberfield</b>. Set ADMIN_USERNAME and ADMIN_PASSWORD in .env before going live.</p>}
    </form>
  );
}
