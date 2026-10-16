import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "../api";

const GOLD = "#d4af37", GOLD2 = "#f5d77a", GRID = "rgba(255,255,255,.06)";
const tip = { contentStyle: { background: "#111", border: "1px solid rgba(212,175,55,.3)", borderRadius: 8, fontSize: 12 }, labelStyle: { color: GOLD2 } };

function Card({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: boolean }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${accent ? "text-red-300" : "gold-text"}`}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Analytics() {
  const [days, setDays] = useState(30);
  const [a, setA] = useState<any>(null);
  useEffect(() => { api(`/api/analytics?days=${days}`).then(setA); }, [days]);
  if (!a) return <div className="text-sm text-zinc-500 p-4">Loading…</div>;
  const peak = [...a.busy_hours].sort((x: any, y: any) => y.messages - x.messages)[0];
  return (
    <div className="space-y-5" data-testid="analytics">
      <div className="flex items-center gap-2">
        <div className="text-sm text-zinc-400">Last</div>
        {[7, 30, 90].map((d) => <button key={d} onClick={() => setDays(d)} className={`chip border ${d === days ? "bg-gold-500 text-black border-gold-500" : "border-white/15 text-zinc-300"}`}>{d} days</button>)}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
        <Card label="Chats" value={a.chats} sub={`${a.messages_in} messages`} />
        <Card label="Orders" value={a.orders} />
        <Card label="Revenue" value={`₹${a.revenue.toLocaleString("en-IN")}`} sub={`₹${a.revenue_paid.toLocaleString("en-IN")} paid online`} />
        <Card label="Bookings" value={a.bookings} />
        <Card label="Leads" value={a.leads} />
        <Card label="Missed" value={a.missed} sub="bot couldn't answer" accent />
        <Card label="Handoffs" value={a.handoffs} sub={`${a.waiting_now} waiting now`} accent />
      </div>
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card p-4">
          <div className="flex items-baseline"><div className="text-sm font-semibold text-gold-300">Busy hours</div>
            {peak?.messages > 0 && <div className="ml-auto text-xs text-zinc-400">Peak: {peak.label} ({peak.messages} msgs)</div>}</div>
          <div className="h-64 mt-2"><ResponsiveContainer><BarChart data={a.busy_hours}>
            <CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 11 }} interval={1} />
            <YAxis allowDecimals={false} tick={{ fill: "#a1a1aa", fontSize: 11 }} width={28} /><Tooltip {...tip} cursor={{ fill: "rgba(212,175,55,.08)" }} />
            <Bar dataKey="messages" fill={GOLD} radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </div>
        <div className="card p-4">
          <div className="text-sm font-semibold text-gold-300">Last 14 days</div>
          <div className="h-64 mt-2"><ResponsiveContainer><LineChart data={a.daily}>
            <CartesianGrid stroke={GRID} vertical={false} /><XAxis dataKey="date" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
            <YAxis allowDecimals={false} tick={{ fill: "#a1a1aa", fontSize: 11 }} width={28} /><Tooltip {...tip} /><Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="chats" stroke={GOLD} strokeWidth={2} dot={false} /><Line type="monotone" dataKey="orders" stroke="#34d399" strokeWidth={2} dot={false} />
          </LineChart></ResponsiveContainer></div>
        </div>
      </div>
      <div className="card p-4">
        <div className="text-sm font-semibold text-gold-300 mb-2">What customers asked for</div>
        <div className="flex flex-wrap gap-2">{a.intents.map((i: any) => (
          <span key={i.intent} className="chip bg-gold-500/10 text-gold-200 border border-gold-500/20">{i.intent.replace(/_/g, " ")} · {i.n}</span>))}</div>
      </div>
    </div>
  );
}
