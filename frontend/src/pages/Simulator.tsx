import { useEffect, useRef, useState } from "react";
import { post } from "../api";

type UI = { kind: "buttons"; buttons: { id: string; title: string }[] } | { kind: "list"; button: string; sections: { title: string; rows: { id: string; title: string; description?: string }[] }[] };
type Msg = { from: "me" | "bot"; text: string; meta?: string; ui?: UI | null };
const PERSONAS = [
  { phone: "+919876500001", name: "Ananya", lang: "English" },
  { phone: "+919876500002", name: "Vikram", lang: "हिन्दी" },
  { phone: "+919876500003", name: "Lakshmi", lang: "தமிழ்" },
];
const QUICK: Record<string, string[]> = {
  English: ["Hi", "Menu", "2 masala dosa and 2 filter coffee", "confirm", "PICKUP", "Book a table", "Do you deliver?", "Catering for 50 people", "Talk to a human"],
  "हिन्दी": ["नमस्ते", "मेनू", "1 बिरयानी और 2 लस्सी", "confirm", "टेबल बुक करना है", "आप कितने बजे खुलते हैं?", "मैनेजर से बात करनी है"],
  "தமிழ்": ["வணக்கம்", "மெனு", "2 தோசை 1 காபி", "confirm", "டேபிள் முன்பதிவு", "டெலிவரி இருக்கா?", "மேலாளரிடம் பேச வேண்டும்"],
};
const LANG_NAME: Record<string, string> = { en: "English", hi: "Hindi", ta: "Tamil" };

function Interactive({ ui, onPick }: { ui: UI; onPick: (id: string, title: string) => void }) {
  const [open, setOpen] = useState(false);
  if (ui.kind === "buttons") return (
    <div className="mt-1 grid gap-1" data-testid="wa-buttons">{ui.buttons.map((b) => (
      <button key={b.id} data-testid={`btn-${b.id}`} onClick={() => onPick(b.id, b.title)} className="rounded-lg bg-[#202c33] py-1.5 text-[13px] text-[#53bdeb] hover:bg-[#2a3942]">{b.title}</button>))}
    </div>);
  return (
    <div className="mt-1" data-testid="wa-list">
      <button onClick={() => setOpen(!open)} className="w-full rounded-lg bg-[#202c33] py-1.5 text-[13px] text-[#53bdeb] hover:bg-[#2a3942]">☰ {ui.button}</button>
      {open && <div className="mt-1 rounded-lg bg-[#202c33] p-1">{ui.sections.map((s) => (
        <div key={s.title}><div className="px-2 pt-1 text-[10px] uppercase text-emerald-400">{s.title}</div>
          {s.rows.map((r) => (<button key={r.id} data-testid={`row-${r.id}`} onClick={() => { setOpen(false); onPick(r.id, r.title); }}
            className="block w-full text-left px-2 py-1.5 rounded hover:bg-white/5"><div className="text-[13px] text-white">{r.title}</div>
            {r.description && <div className="text-[11px] text-zinc-400">{r.description}</div>}</button>))}</div>))}</div>}
    </div>);
}

function Bubble({ m }: { m: Msg }) {
  const html = m.text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/\*(.+?)\*/g, "<b>$1</b>").replace(/(^|\s)_(.+?)_/g, "$1<i>$2</i>");
  return (
    <div className={`flex ${m.from === "me" ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[82%] rounded-lg px-2.5 py-1.5 text-[13px] leading-snug shadow whitespace-pre-wrap ${m.from === "me" ? "bg-[#005c4b] text-white rounded-tr-none" : "bg-[#202c33] text-zinc-100 rounded-tl-none"}`}>
        <span dangerouslySetInnerHTML={{ __html: html }} />
        <div className="text-[10px] text-white/50 text-right mt-0.5">{m.meta ?? ""} {m.from === "me" ? "✓✓" : ""}</div>
      </div>
    </div>
  );
}

export default function Simulator() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  const [msgs, setMsgs] = useState<Record<string, Msg[]>>({});
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<{ intent: string; lang: string } | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const thread = msgs[persona.phone] ?? [];
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [thread.length]);

  async function send(t: string, opts: { type?: "text" | "audio" | "image"; action?: string } = {}) {
    if (!t.trim()) return;
    const type = opts.type ?? "text";
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const add = (m: Msg) => setMsgs((s) => ({ ...s, [persona.phone]: [...(s[persona.phone] ?? []), m] }));
    add({ from: "me", text: type === "audio" ? `🎤 Voice note\n_“${t}”_` : type === "image" ? `📷 Photo\n${t}` : t, meta: now });
    setText(""); setBusy(true);
    try {
      const r = await post("/api/simulate", { phone: persona.phone, name: persona.name, text: t, type, action: opts.action });
      setLast({ intent: r.intent, lang: r.lang });
      add({ from: "bot", text: r.reply ?? "⏳ A team member has been notified and will reply here.", meta: now, ui: r.interactive });
    } finally { setBusy(false); }
  }
  const lastBot = [...thread].reverse().find((m) => m.from === "bot");

  return (
    <div className="grid lg:grid-cols-[1fr_380px_1fr] gap-8 items-start">
      <section className="space-y-5">
        <h1 className="font-display text-3xl font-bold leading-tight"><span className="gold-text">24/7 WhatsApp sales</span><br />for your business</h1>
        <p className="text-zinc-400 text-sm leading-relaxed">We built this assistant to answer FAQs, take orders, book tables, capture leads and hand off to your team — in English, Hindi and Tamil. Try it as a customer on the phone.</p>
        <div className="card p-4 space-y-2">
          <div className="text-xs uppercase tracking-wider text-gold-400/80 font-semibold">Chat as</div>
          {PERSONAS.map((p) => (
            <button key={p.phone} data-testid={`persona-${p.name}`} onClick={() => setPersona(p)}
              className={`w-full flex items-center gap-3 rounded-xl px-3 py-2 text-left transition ${persona.phone === p.phone ? "bg-gold-500/15 border border-gold-500/40" : "hover:bg-white/5 border border-transparent"}`}>
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-gold-300 to-gold-700 text-black grid place-items-center font-bold text-sm">{p.name[0]}</div>
              <div><div className="text-sm font-medium">{p.name}</div><div className="text-xs text-zinc-500">{p.lang} · {p.phone}</div></div>
            </button>
          ))}
        </div>
      </section>

      <div className="mx-auto w-[360px] rounded-[2.6rem] border-[10px] border-zinc-900 bg-black shadow-[0_0_60px_-10px_rgba(212,175,55,.35)] ring-1 ring-gold-500/30 overflow-hidden">
        <div className="h-6 bg-[#111b21] flex justify-center"><div className="h-4 w-24 rounded-b-xl bg-black" /></div>
        <div className="bg-[#202c33] px-3 py-2.5 flex items-center gap-2.5">
          <img src="/logo.svg" className="h-8 w-8 rounded-full bg-black p-1" />
          <div><div className="text-sm font-semibold text-white">Spice Route Kitchen</div><div className="text-[11px] text-emerald-400">{busy ? "typing…" : "online · Business account"}</div></div>
        </div>
        <div data-testid="chat" className="h-[470px] overflow-y-auto p-3 space-y-1.5 bg-[#0b141a] bg-[radial-gradient(rgba(255,255,255,.03)_1px,transparent_1px)] [background-size:14px_14px]">
          <div className="text-center"><span className="chip bg-[#182229] text-[#8696a0]">Messages are simulated · demo mode</span></div>
          {thread.map((m, i) => <div key={i}><Bubble m={m} />
            {m.ui && m === lastBot && <div className="max-w-[82%]"><Interactive ui={m.ui} onPick={(id, title) => send(title, { action: id })} /></div>}</div>)}
          <div ref={end} />
        </div>
        <form className="bg-[#202c33] p-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <input data-testid="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message"
            className="flex-1 rounded-full bg-[#2a3942] px-4 py-2 text-sm text-white outline-none" />
          <button type="button" data-testid="chat-voice" title="Send as a voice note (mock transcript)" disabled={busy || !text.trim()} onClick={() => send(text, { type: "audio" })} className="h-9 w-9 rounded-full text-zinc-300 hover:bg-white/10 disabled:opacity-40">🎤</button>
          <button type="button" data-testid="chat-photo" title="Send as a photo (mock: describe what's in it)" disabled={busy || !text.trim()} onClick={() => send(text, { type: "image" })} className="h-9 w-9 rounded-full text-zinc-300 hover:bg-white/10 disabled:opacity-40">📷</button>
          <button data-testid="chat-send" disabled={busy} className="h-9 w-9 rounded-full bg-[#00a884] text-white grid place-items-center">➤</button>
        </form>
      </div>

      <section className="space-y-5">
        <div className="card p-4">
          <div className="text-xs uppercase tracking-wider text-gold-400/80 font-semibold mb-3">Try these</div>
          <div className="flex flex-wrap gap-2">
            {QUICK[persona.lang].map((q) => (
              <button key={q} onClick={() => send(q)} className="rounded-full border border-gold-500/30 px-3 py-1 text-xs text-gold-200 hover:bg-gold-500/10">{q}</button>
            ))}
          </div>
        </div>
        <div className="card p-4" data-testid="ai-insight">
          <div className="text-xs uppercase tracking-wider text-gold-400/80 font-semibold mb-3">AI understanding</div>
          {last ? (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-zinc-500 text-xs">Intent</div><div className="font-semibold text-gold-300 capitalize">{last.intent.replace("_", " ")}</div></div>
              <div><div className="text-zinc-500 text-xs">Language</div><div className="font-semibold text-gold-300">{LANG_NAME[last.lang]}</div></div>
            </div>
          ) : <div className="text-sm text-zinc-500">Send a message to see detected intent and language.</div>}
        </div>
        <div className="card p-4 text-xs text-zinc-400 leading-relaxed">
          <b className="text-gold-300">Voice & photos:</b> type a message and tap 🎤 to send it as a voice note (we mock the transcript), or 📷 to send a photo described by your text, e.g. “photo of 2 butter chicken” or “prescription: paracetamol 500mg”. Live, we transcribe with Whisper and read photos with a vision model.<br /><br />
          <b className="text-gold-300">Production-ready path:</b> the same engine sits behind a WhatsApp Cloud API webhook (<code className="text-gold-200">/webhook</code>). Outbound messages stay simulated until your Meta keys are configured, and every broadcast waits for owner approval.
        </div>
      </section>
    </div>
  );
}
