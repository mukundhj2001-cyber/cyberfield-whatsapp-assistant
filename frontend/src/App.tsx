import { useEffect, useState } from "react";
import { api, post, getBusiness, setBusiness } from "./api";
import Login from "./pages/Login";
import Simulator from "./pages/Simulator";
import Dashboard from "./pages/Dashboard";

type Biz = { id: number; name: string; kind: string; tagline: string };
type Health = { llm: string; whatsapp: string; auth: string; business: { name: string; type: string } };

export default function App() {
  const [tab, setTab] = useState<"sim" | "dash">(location.hash === "#dashboard" ? "dash" : "sim");
  const [health, setHealth] = useState<Health | null>(null);
  const [user, setUser] = useState<string | null | undefined>(undefined);
  const [bizList, setBizList] = useState<Biz[]>([]);
  const [biz, setBiz] = useState<string>(getBusiness());
  useEffect(() => { api<Biz[]>("/api/public/businesses").then((l) => { setBizList(l); if (!l.find((b) => String(b.id) === getBusiness()) && l[0]) { setBusiness(String(l[0].id)); setBiz(String(l[0].id)); } }).catch(() => {}); }, []);
  const current = bizList.find((b) => String(b.id) === biz);
  useEffect(() => { api<Health>("/api/health").then(setHealth).catch(() => {}); }, []);
  useEffect(() => { api<{ user: string | null }>("/api/auth/me").then((r) => setUser(r.user)).catch(() => setUser(null)); }, []);
  useEffect(() => { const f = () => setUser(null); window.addEventListener("auth-required", f); return () => window.removeEventListener("auth-required", f); }, []);
  useEffect(() => { location.hash = tab === "dash" ? "dashboard" : "simulator"; }, [tab]);
  return (
    <div className="min-h-screen">
      <header className="border-b border-gold-500/15 bg-black/60 backdrop-blur sticky top-0 z-20">
        <div className="mx-auto max-w-7xl flex items-center gap-4 px-6 py-3">
          <img src="/logo.svg" className="h-9 w-9" alt="Cyberfield AI" />
          <div>
            <div className="font-display text-sm tracking-[0.25em] gold-text font-bold">CYBERFIELD AI</div>
            <div className="text-xs text-zinc-400">WhatsApp Business Assistant · {current?.name ?? health?.business.name ?? "…"}</div>
          </div>
          <nav className="ml-8 flex gap-1 rounded-xl bg-ink-700 p-1">
            {([["sim", "Live chat demo"], ["dash", "Owner dashboard"]] as const).map(([k, l]) => (
              <button key={k} data-testid={`tab-${k}`} onClick={() => setTab(k)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${tab === k ? "bg-gold-500 text-black" : "text-zinc-300 hover:text-gold-300"}`}>{l}</button>
            ))}
          </nav>
          <select data-testid="biz-select" value={biz} onChange={(e) => { setBusiness(e.target.value); setBiz(e.target.value); }}
            className="ml-4 rounded-lg bg-ink-700 border border-gold-500/30 px-2 py-1.5 text-xs text-gold-200 outline-none" title="Business">
            {bizList.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <div className="ml-auto flex gap-2 text-xs">
            <span className="chip bg-gold-500/10 text-gold-300 border border-gold-500/30">AI: {health?.llm === "live" ? "LLM live" : "demo mode"}</span>
            <span className="chip bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">WhatsApp: {health?.whatsapp ?? "…"}</span>
            {user && <button data-testid="logout" className="chip border border-white/15 text-zinc-300 hover:text-gold-300" onClick={async () => { await post("/api/auth/logout"); setUser(null); }}>Log out</button>}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{tab === "sim" ? <Simulator key={biz} biz={current} /> : user ? <Dashboard key={biz} biz={current} /> : user === null ? <Login demo={health?.auth !== "configured"} onDone={setUser} /> : null}</main>
      <footer className="text-center text-xs text-zinc-500 pb-6">Built by <span className="text-gold-400">Cyberfield AI</span> · demo data is fictional</footer>
    </div>
  );
}
