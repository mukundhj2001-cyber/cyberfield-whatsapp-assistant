import { useEffect, useState } from "react";
import { api, post } from "../api";
import Analytics from "./Analytics";
import Settings from "./Settings";

const TABS = ["Conversations", "Orders", "Bookings", "Leads", "Handoff queue", "Broadcasts", "Analytics", "Settings"] as const;
type Tab = (typeof TABS)[number];
const LANG: Record<string, string> = { en: "EN", hi: "हि", ta: "த" };
const fmt = (s: string) => new Date(s.replace(" ", "T") + (s.includes("T") ? "" : "Z")).toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent ? "text-red-300" : "gold-text"}`}>{value}</div>
    </div>
  );
}
const Status = ({ s }: { s: string }) => {
  const c: Record<string, string> = { new: "bg-sky-500/15 text-sky-300", confirmed: "bg-emerald-500/15 text-emerald-300", sent: "bg-emerald-500/15 text-emerald-300",
    pending_approval: "bg-amber-500/15 text-amber-300", paid: "bg-emerald-500/15 text-emerald-300", unpaid: "bg-zinc-500/20 text-zinc-300", rejected: "bg-red-500/15 text-red-300", preparing: "bg-amber-500/15 text-amber-300", completed: "bg-emerald-500/15 text-emerald-300" };
  return <span className={`chip ${c[s] ?? "bg-white/10"}`}>{s.replace(/_/g, " ")}</span>;
};

export default function Dashboard({ biz }: { biz?: { name: string; kind: string } }) {
  const [tab, setTab] = useState<Tab>("Conversations");
  const [stats, setStats] = useState<any>({});
  const [data, setData] = useState<Record<string, any[]>>({});
  const [sel, setSel] = useState<any | null>(null);
  const [thread, setThread] = useState<any[]>([]);
  const [reply, setReply] = useState("");
  const [draft, setDraft] = useState<{ title: string; body: string; template_id?: number }>({ title: "", body: "" });
  const [tpls, setTpls] = useState<any[]>([]);
  const [note, setNote] = useState("");
  const flash = (m: string) => { setNote(m); setTimeout(() => setNote(""), 3500); };

  async function load() {
    const [s, c, o, b, l, h, br] = await Promise.all(["stats", "conversations", "orders", "bookings", "leads", "handoffs", "broadcasts"].map((p) => api(`/api/${p}`)));
    setStats(s); setData({ c, o, b, l, h, br });
    api("/api/settings").then((r) => setTpls(r.templates)).catch(() => {});
  }
  useEffect(() => { load(); }, []);
  async function open(c: any) { setSel(c); setThread(await api(`/api/conversations/${c.id}/messages`)); }
  async function sendReply() { if (!sel || !reply) return; try { await post(`/api/conversations/${sel.id}/reply`, { text: reply }); setReply(""); open(sel); load(); } catch (e: any) { flash(e.message); } }
  async function resolve(c: any) { await post(`/api/conversations/${c.id}/resolve`); load(); }

  const convTable = (rows: any[], handoff = false) => (
    <div className="grid lg:grid-cols-[1.1fr_1fr] gap-5">
      <table className="w-full"><thead><tr><th>Customer</th><th>Lang</th><th>{handoff ? "Reason" : "Last message"}</th><th></th></tr></thead>
        <tbody>{rows.map((c) => (
          <tr key={c.id} onClick={() => open(c)} className={`cursor-pointer hover:bg-white/5 ${sel?.id === c.id ? "bg-gold-500/10" : ""}`}>
            <td><div className="font-medium">{c.name}</div><div className="text-xs text-zinc-500">{c.phone}</div></td>
            <td><span className="chip bg-gold-500/15 text-gold-300">{LANG[c.lang]}</span></td>
            <td className="text-zinc-400 max-w-xs truncate">{handoff ? c.handoff_reason : c.last_text?.slice(0, 70)}</td>
            <td>{c.needs_human ? <span className="chip bg-red-500/15 text-red-300">needs human</span> : <span className="chip bg-emerald-500/10 text-emerald-300">bot</span>}</td>
          </tr>))}
        </tbody></table>
      <div className="card p-4 min-h-[300px]" data-testid="thread">
        {!sel ? <div className="text-sm text-zinc-500">Select a conversation to read the transcript.</div> : (
          <div className="flex flex-col h-full">
            <div className="flex items-center mb-3"><div className="font-semibold">{sel.name}</div>
              {sel.needs_human ? <button className="btn-ghost ml-auto !py-1" onClick={() => resolve(sel)}>Mark resolved · return to bot</button> : null}</div>
            <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">{thread.map((m) => (
              <div key={m.id} className={`flex ${m.direction === "in" ? "justify-start" : "justify-end"}`}>
                <div className={`max-w-[85%] rounded-lg px-2.5 py-1.5 text-xs whitespace-pre-wrap ${m.direction === "in" ? "bg-ink-600" : m.sender === "owner" ? "bg-gold-500/20 border border-gold-500/40" : "bg-[#005c4b]/70"}`}>
                  {m.text}<div className="text-[10px] text-zinc-400 mt-0.5">{m.sender} · {m.intent}</div></div></div>))}
            </div>
            <div className="flex gap-2 mt-3"><input className="input" value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Reply as the business owner…" />
              <button className="btn-gold" onClick={sendReply}>Send</button></div>
          </div>)}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-end"><div><h1 className="font-display text-2xl font-bold gold-text">Owner dashboard</h1>
        <p className="text-sm text-zinc-400">{biz?.name}: everything your WhatsApp assistant handled — orders, bookings, leads and chats that need you.</p></div>
        {note && <span className="ml-4 chip bg-amber-500/15 text-amber-200" data-testid="note">{note}</span>}
        <button className="btn-ghost ml-auto" onClick={load}>↻ Refresh</button></div>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4" data-testid="stats">
        <Stat label="Conversations" value={stats.conversations ?? "–"} /><Stat label="Orders" value={stats.orders ?? "–"} />
        <Stat label="Revenue" value={`₹${stats.revenue ?? 0}`} /><Stat label="Bookings" value={stats.bookings ?? "–"} />
        <Stat label="Leads" value={stats.leads ?? "–"} /><Stat label="Needs human" value={stats.handoffs ?? "–"} accent />
      </div>
      <div className="flex gap-1 border-b border-white/10">{TABS.map((t) => (
        <button key={t} data-testid={`dash-${t}`} onClick={() => setTab(t)} className={`px-4 py-2 text-sm -mb-px border-b-2 ${tab === t ? "border-gold-500 text-gold-300" : "border-transparent text-zinc-400 hover:text-zinc-200"}`}>
          {t}{t === "Handoff queue" && stats.handoffs ? <span className="ml-1.5 chip bg-red-500/80 text-white">{stats.handoffs}</span> : null}
          {t === "Broadcasts" && stats.pending_broadcasts ? <span className="ml-1.5 chip bg-amber-500/80 text-black">{stats.pending_broadcasts}</span> : null}</button>))}
      </div>
      <div className="card p-4">
        {tab === "Conversations" && convTable(data.c ?? [])}
        {tab === "Handoff queue" && (data.h?.length ? convTable(data.h, true) : <div className="text-sm text-zinc-500 p-4">No one is waiting. 🎉</div>)}
        {tab === "Orders" && (
          <table className="w-full"><thead><tr><th>#</th><th>Customer</th><th>Items</th><th>Total</th><th>Fulfilment</th><th>Payment</th><th>Status</th></tr></thead>
            <tbody>{(data.o ?? []).map((o) => (<tr key={o.id}><td className="text-gold-300">#{o.id}</td><td>{o.customer}</td>
              <td>{o.items.map((i: any) => `${i.qty}× ${i.name}`).join(", ")}</td><td className="font-semibold">₹{o.total}</td><td className="text-zinc-400">{o.fulfilment}</td>
              <td><Status s={o.payment_status ?? "unpaid"} />{o.payment_provider && <div className="text-[11px] text-zinc-500 mt-0.5">{o.payment_provider}</div>}
                {o.payment_status !== "paid" && <button className="text-[11px] text-gold-300 hover:underline block" onClick={async () => { await post(`/api/orders/${o.id}/paid`); load(); }}>Mark paid</button>}</td>
              <td><select className="input !w-auto !py-1" value={o.status} onChange={async (e) => { await api(`/api/orders/${o.id}`, { method: "PATCH", body: JSON.stringify({ status: e.target.value }) }); load(); }}>
                {["new", "preparing", "out_for_delivery", "completed", "cancelled"].map((s) => <option key={s}>{s}</option>)}</select></td></tr>))}</tbody></table>)}
        {tab === "Bookings" && (
          <table className="w-full"><thead><tr><th>Code</th><th>Customer</th><th>When</th><th>{biz?.kind === "restaurant" ? "Party" : "Service"}</th><th>Status</th><th></th></tr></thead>
            <tbody>{(data.b ?? []).map((b) => (<tr key={b.id}><td className="text-gold-300 font-mono">{b.code}</td><td>{b.customer}<div className="text-xs text-zinc-500">{b.phone}</div></td>
              <td>{new Date(b.starts_at).toLocaleString([], { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</td><td>{biz?.kind === "restaurant" ? b.party_size : b.service ?? "–"}</td><td><Status s={b.status} /></td>
              <td><button className="btn-ghost !py-1 !px-2 text-xs" onClick={async () => { try { const r = await post(`/api/bookings/${b.id}/remind`); flash(`Reminder sent as ${r.via}${r.template ? ` (${r.template})` : ""}: ${r.delivery}`); load(); } catch (e: any) { flash(e.message); } }}>
                ⏰ Remind</button>{b.reminded_at && <div className="text-[10px] text-zinc-500">reminded {fmt(b.reminded_at)}</div>}</td></tr>))}</tbody></table>)}
        {tab === "Leads" && (
          <table className="w-full"><thead><tr><th>Name</th><th>Contact</th><th>Interest</th><th>Captured</th><th>Status</th></tr></thead>
            <tbody>{(data.l ?? []).map((l) => (<tr key={l.id}><td className="font-medium">{l.name}</td><td className="text-gold-300">{l.contact}</td><td className="text-zinc-400">{l.interest}</td>
              <td className="text-zinc-500">{fmt(l.created_at)}</td><td><Status s={l.status} /></td></tr>))}</tbody></table>)}
        {tab === "Broadcasts" && (
          <div className="grid lg:grid-cols-[1fr_1.4fr] gap-6">
            <div className="space-y-3"><div className="text-sm font-semibold text-gold-300">New broadcast</div>
              <input className="input" placeholder="Title" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
              <textarea className="input h-28" placeholder="Message to all customers…" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
              <select className="input" value={draft.template_id ?? ""} onChange={(e) => setDraft({ ...draft, template_id: e.target.value ? +e.target.value : undefined })}>
                <option value="">No template: only customers who messaged in the last 24h</option>
                {tpls.map((t) => <option key={t.id} value={t.id}>Template: {t.name} ({t.language}) for customers outside 24h</option>)}</select>
              <button className="btn-gold" disabled={!draft.title || !draft.body} onClick={async () => { await post("/api/broadcasts", draft); setDraft({ title: "", body: "" }); load(); }}>Submit for approval</button>
              <p className="text-xs text-zinc-500">Nothing is sent until an owner approves it. WhatsApp only allows free text within 24h of a customer's last message. Everyone else gets the approved template, or is skipped. Without Meta API keys, sends are simulated and logged.</p></div>
            <div className="space-y-3">{(data.br ?? []).map((b) => (
              <div key={b.id} className="rounded-xl border border-white/10 p-3" data-testid="broadcast">
                <div className="flex items-center gap-2"><div className="font-semibold">{b.title}</div><Status s={b.status} />
                  {b.status === "sent" && <span className="text-xs text-zinc-500">to {b.recipients} customers{b.skipped ? ` · ${b.skipped} skipped (outside 24h, no template)` : ""}</span>}</div>
                <p className="text-sm text-zinc-400 mt-1">{b.body}</p>
                {b.status === "pending_approval" && <div className="flex gap-2 mt-2">
                  <button className="btn-gold !py-1" onClick={async () => { await post(`/api/broadcasts/${b.id}/approve`); load(); }}>Approve & send</button>
                  <button className="btn-ghost !py-1" onClick={async () => { await post(`/api/broadcasts/${b.id}/reject`); load(); }}>Reject</button></div>}
              </div>))}</div>
          </div>)}
        {tab === "Analytics" && <Analytics />}
        {tab === "Settings" && <Settings />}
      </div>
    </div>
  );
}
