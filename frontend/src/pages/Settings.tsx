import { useEffect, useState } from "react";
import { api, del, post, put } from "../api";

const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["ta", "தமிழ்"]] as const;
const Section = ({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) => (
  <div className="card p-5 space-y-3"><div><div className="font-semibold text-gold-300">{title}</div>{hint && <div className="text-xs text-zinc-500">{hint}</div>}</div>{children}</div>
);
const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <label className="block"><div className="text-xs text-zinc-400 mb-1">{label}</div>{children}</label>
);

// One editable row; saves on "Save", deletes on "✕"
function Row({ item, fields, kind, onChange }: { item: any; fields: [string, string, string?][]; kind: string; onChange: () => void }) {
  const [d, setD] = useState<any>(item);
  const dirty = JSON.stringify(d) !== JSON.stringify(item);
  return (
    <tr>{fields.map(([k, , type]) => (
      <td key={k} className="!px-1.5">{type === "area" ? <textarea className="input !py-1 h-16" value={d[k] ?? ""} onChange={(e) => setD({ ...d, [k]: e.target.value })} />
        : <input className="input !py-1" type={type ?? "text"} value={Array.isArray(d[k]) ? d[k].join(", ") : d[k] ?? ""} onChange={(e) => setD({ ...d, [k]: e.target.value })} />}</td>))}
      <td className="!px-1.5 whitespace-nowrap">
        <button className="btn-gold !py-1 !px-2" disabled={!dirty} onClick={async () => { await put(`/api/settings/${kind}/${item.id}`, d); onChange(); }}>Save</button>
        <button className="btn-ghost !py-1 !px-2 ml-1" title="Delete" onClick={async () => { if (confirm("Delete?")) { try { await del(`/api/settings/${kind}/${item.id}`); onChange(); } catch (e: any) { alert(e.message); } } }}>✕</button>
      </td></tr>
  );
}

function Table({ rows, fields, kind, onChange, blank }: { rows: any[]; fields: [string, string, string?][]; kind: string; onChange: () => void; blank: any }) {
  const [n, setN] = useState<any>(blank);
  return (
    <div className="overflow-x-auto"><table className="w-full" data-testid={`settings-${kind}`}>
      <thead><tr>{fields.map(([k, l]) => <th key={k}>{l}</th>)}<th></th></tr></thead>
      <tbody>{rows.map((r) => <Row key={r.id + JSON.stringify(r)} item={r} fields={fields} kind={kind} onChange={onChange} />)}
        <tr className="bg-gold-500/5">{fields.map(([k, l, type]) => (
          <td key={k} className="!px-1.5"><input className="input !py-1" type={type === "area" ? "text" : type ?? "text"} placeholder={`New ${l.toLowerCase()}`} value={n[k] ?? ""} onChange={(e) => setN({ ...n, [k]: e.target.value })} /></td>))}
          <td className="!px-1.5"><button className="btn-gold !py-1 !px-2" onClick={async () => { try { await post(`/api/settings/${kind}`, n); setN(blank); onChange(); } catch (e: any) { alert(e.message); } }}>Add</button></td></tr>
      </tbody></table></div>
  );
}

export default function Settings() {
  const [s, setS] = useState<any>(null);
  const [biz, setBiz] = useState<any>({});
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState("");
  const [gen, setGen] = useState({ days: 7, hours: "10, 12, 15, 18", capacity: 1 });
  const load = () => api("/api/settings").then((r) => { setS(r); setBiz(r.business); });
  useEffect(() => { load(); }, []);
  if (!s) return <div className="text-sm text-zinc-500 p-4">Loading…</div>;
  const flash = (m: string) => { setSaved(m); setTimeout(() => setSaved(""), 2500); };
  async function saveBiz() {
    try {
      await put("/api/settings/business", { name: biz.name, tagline: biz.tagline, hours: biz.hours, languages: biz.languages, default_lang: biz.default_lang,
        upi_id: biz.upi_id ?? "", phone_number_id: biz.phone_number_id ?? "", wa_token: token, orders_enabled: !!biz.orders_enabled });
      setToken(""); load(); flash("Saved ✓");
    } catch (e: any) { alert(e.message); }
  }
  const toggleLang = (l: string) => setBiz({ ...biz, languages: biz.languages.includes(l) ? biz.languages.filter((x: string) => x !== l) : [...biz.languages, l] });
  return (
    <div className="space-y-5" data-testid="settings">
      <Section title="Business profile" hint="What customers see, which WhatsApp number this business answers on, and how they pay.">
        <div className="grid md:grid-cols-3 gap-3">
          <Field label="Business name"><input data-testid="biz-name" className="input" value={biz.name ?? ""} onChange={(e) => setBiz({ ...biz, name: e.target.value })} /></Field>
          <Field label="Tagline"><input className="input" value={biz.tagline ?? ""} onChange={(e) => setBiz({ ...biz, tagline: e.target.value })} /></Field>
          <Field label="UPI ID (for payment links when Razorpay isn't set)"><input className="input" placeholder="yourshop@okhdfcbank" value={biz.upi_id ?? ""} onChange={(e) => setBiz({ ...biz, upi_id: e.target.value })} /></Field>
          <Field label="WhatsApp phone_number_id"><input className="input" placeholder={biz.id === 1 ? "blank = use WHATSAPP_PHONE_NUMBER_ID" : "from Meta > WhatsApp > API Setup"} value={biz.phone_number_id ?? ""} onChange={(e) => setBiz({ ...biz, phone_number_id: e.target.value })} /></Field>
          <Field label={`WhatsApp token ${biz.has_token ? "(set: leave blank to keep)" : "(blank = use WHATSAPP_TOKEN)"}`}><input className="input" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="••••••" /></Field>
          <Field label="Status"><div className="flex gap-2 pt-1.5">
            <span className={`chip ${biz.live ? "bg-emerald-500/15 text-emerald-300" : "bg-white/10 text-zinc-300"}`}>{biz.live ? "sending live" : "simulated"}</span>
            <span className="chip bg-gold-500/10 text-gold-300">payments: {s.payments.mode}</span></div></Field>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="text-xs text-zinc-400">Languages:</div>
          {LANGS.map(([k, l]) => <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={biz.languages?.includes(k)} onChange={() => toggleLang(k)} />{l}</label>)}
          <label className="flex items-center gap-1.5 text-xs text-zinc-400">Default
            <select className="input !w-auto !py-1" value={biz.default_lang} onChange={(e) => setBiz({ ...biz, default_lang: e.target.value })}>{LANGS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
          <label className="flex items-center gap-1.5"><input type="checkbox" checked={!!biz.orders_enabled} onChange={(e) => setBiz({ ...biz, orders_enabled: e.target.checked ? 1 : 0 })} />Takes orders (off = services are booked as appointments)</label>
        </div>
      </Section>

      <Section title="Opening hours" hint="Used when customers ask about timings, and given to the AI as a fact.">
        <div className="grid md:grid-cols-3 gap-3">{LANGS.map(([k, l]) => (
          <Field key={k} label={l}><input data-testid={`hours-${k}`} className="input" value={biz.hours?.[k] ?? ""} onChange={(e) => setBiz({ ...biz, hours: { ...biz.hours, [k]: e.target.value } })} /></Field>))}</div>
        <div className="flex items-center gap-3"><button data-testid="save-biz" className="btn-gold" onClick={saveBiz}>Save profile & hours</button><span className="text-sm text-emerald-300">{saved}</span></div>
      </Section>

      <Section title="FAQs" hint="Keywords are matched in any language. Give answers in each language you offer; English is used when one is missing.">
        <Table kind="faq" rows={s.faq} onChange={load} blank={{}} fields={[["topic", "Topic"], ["keywords", "Keywords", "area"], ["answer_en", "Answer (EN)", "area"], ["answer_hi", "Answer (HI)", "area"], ["answer_ta", "Answer (TA)", "area"]]} />
      </Section>

      <Section title={biz.orders_enabled ? "Menu" : "Services"} hint="Aliases are other words customers use, comma-separated (e.g. dosa, डोसा, தோசை).">
        <Table kind="menu" rows={s.menu} onChange={load} blank={{}} fields={[["name", "Name"], ["price", "Price ₹", "number"], ["category", "Category"], ["aliases", "Aliases"]]} />
      </Section>

      <Section title="Booking slots" hint="Upcoming times customers can pick. Booked slots can't be deleted.">
        <div className="flex flex-wrap items-end gap-3 text-sm">
          <Field label="Days ahead"><input className="input !w-24" type="number" value={gen.days} onChange={(e) => setGen({ ...gen, days: +e.target.value })} /></Field>
          <Field label="Hours (24h, comma-separated)"><input className="input !w-56" value={gen.hours} onChange={(e) => setGen({ ...gen, hours: e.target.value })} /></Field>
          <Field label="Capacity each"><input className="input !w-24" type="number" value={gen.capacity} onChange={(e) => setGen({ ...gen, capacity: +e.target.value })} /></Field>
          <button className="btn-ghost" onClick={async () => { const r = await post("/api/settings/slots/generate", { days: gen.days, capacity: gen.capacity, hours: gen.hours.split(",").map((x) => parseInt(x)).filter((x) => !isNaN(x)) }); flash(`Added ${r.added} slots`); load(); }}>Generate slots</button>
        </div>
        <div className="max-h-72 overflow-y-auto"><Table kind="slots" rows={s.slots.map((x: any) => ({ ...x }))} onChange={load} blank={{ capacity: 1 }} fields={[["starts_at", "Starts at", "datetime-local"], ["capacity", "Capacity", "number"], ["booked", "Booked"]]} /></div>
      </Section>

      <Section title="Message templates" hint="Create and get templates approved in Meta WhatsApp Manager first, then add the exact name and language here. Used for reminders and offers outside the 24-hour window. Body uses {{1}}, {{2}}… (reminders: 1 = name, 2 = time, 3 = code; offers: 1 = name).">
        <Table kind="templates" rows={s.templates} onChange={load} blank={{ language: "en", category: "UTILITY", purpose: "reminder" }} fields={[["name", "Name"], ["language", "Language"], ["category", "Category"], ["purpose", "Purpose (reminder/offer)"], ["body", "Body preview", "area"]]} />
      </Section>
    </div>
  );
}
