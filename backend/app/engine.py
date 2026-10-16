"""Conversation engine: language detection, intent routing, cart/booking/lead flows, handoff."""
import datetime as dt, json, random, re, string
from . import db, llm

LANGS = ("en", "hi", "ta")
HI_ROMAN = {"namaste", "kya", "hai", "mujhe", "chahiye", "kitna", "kitne", "aap", "kab", "bhai", "haan", "nahi", "karna", "dijiye"}
TA_ROMAN = {"vanakkam", "enna", "venum", "irukka", "sollunga", "evlo", "eppo", "naan", "romba", "nandri", "illa", "aama"}


def detect_lang(text: str) -> str:
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & TA_ROMAN:
        return "ta"
    if words & HI_ROMAN:
        return "hi"
    return "en"


T = {
    "greet": {"en": "Hi {name}! 👋 Welcome to *Spice Route Kitchen*. I can help you:\n• 🍛 Order food — reply *MENU*\n• 📅 Book a table — reply *BOOK*\n• ❓ Ask about hours, delivery, payments\n• 🙋 Talk to our team — reply *HUMAN*",
              "hi": "नमस्ते {name}! 👋 *Spice Route Kitchen* में आपका स्वागत है। मैं मदद कर सकता हूँ:\n• 🍛 खाना ऑर्डर — *MENU* लिखें\n• 📅 टेबल बुक — *BOOK* लिखें\n• ❓ समय, डिलीवरी, भुगतान के सवाल\n• 🙋 हमारी टीम से बात — *HUMAN* लिखें",
              "ta": "வணக்கம் {name}! 👋 *Spice Route Kitchen*-க்கு வரவேற்கிறோம். நான் உதவ முடியும்:\n• 🍛 உணவு ஆர்டர் — *MENU* அனுப்புங்கள்\n• 📅 டேபிள் முன்பதிவு — *BOOK*\n• ❓ நேரம், டெலிவரி, கட்டணம் பற்றிய கேள்விகள்\n• 🙋 எங்கள் குழுவுடன் பேச — *HUMAN*"},
    "menu": {"en": "📋 *Our menu*\n{items}\n\nReply like “2 paneer tikka and 1 lassi” to add to your cart.",
             "hi": "📋 *हमारा मेनू*\n{items}\n\nकार्ट में जोड़ने के लिए लिखें, जैसे “2 paneer tikka और 1 lassi”।",
             "ta": "📋 *எங்கள் மெனு*\n{items}\n\nகார்ட்டில் சேர்க்க “2 paneer tikka, 1 lassi” என்று அனுப்புங்கள்."},
    "cart": {"en": "🛒 *Your cart*\n{lines}\n*Total: ₹{total}*\n\nReply *CONFIRM* to place the order, add more items, or *CANCEL*.",
             "hi": "🛒 *आपका कार्ट*\n{lines}\n*कुल: ₹{total}*\n\nऑर्डर के लिए *CONFIRM* लिखें, और आइटम जोड़ें, या *CANCEL*।",
             "ta": "🛒 *உங்கள் கார்ட்*\n{lines}\n*மொத்தம்: ₹{total}*\n\nஆர்டர் செய்ய *CONFIRM*, மேலும் சேர்க்கலாம், அல்லது *CANCEL*."},
    "cart_empty": {"en": "Your cart is empty. Reply *MENU* to see what we're cooking today.",
                   "hi": "आपका कार्ट खाली है। *MENU* लिखकर आज का मेनू देखें।",
                   "ta": "உங்கள் கார்ட் காலியாக உள்ளது. *MENU* அனுப்பி இன்றைய மெனுவைப் பாருங்கள்."},
    "ask_address": {"en": "Great! Please send your delivery address, or reply *PICKUP* to collect it yourself.",
                    "hi": "बढ़िया! कृपया डिलीवरी का पता भेजें, या खुद लेने के लिए *PICKUP* लिखें।",
                    "ta": "அருமை! டெலிவரி முகவரியை அனுப்புங்கள், அல்லது நேரில் பெற *PICKUP* என்று அனுப்புங்கள்."},
    "order_done": {"en": "✅ Order *#{id}* placed — ₹{total} ({fulfil}). We'll message you when it's on the way. Thank you!",
                   "hi": "✅ ऑर्डर *#{id}* हो गया — ₹{total} ({fulfil})। रवाना होते ही हम आपको बताएँगे। धन्यवाद!",
                   "ta": "✅ ஆர்டர் *#{id}* பதிவாகியது — ₹{total} ({fulfil}). புறப்பட்டதும் தெரிவிப்போம். நன்றி!"},
    "cancelled": {"en": "No problem — I've cleared that. Anything else?", "hi": "कोई बात नहीं — रद्द कर दिया। और कुछ?",
                  "ta": "சரி — ரத்து செய்துவிட்டேன். வேறு ஏதாவது?"},
    "slots": {"en": "📅 *Available tables*\n{slots}\n\nReply with the slot number (e.g. *2*).",
              "hi": "📅 *उपलब्ध टेबल*\n{slots}\n\nस्लॉट नंबर भेजें (जैसे *2*)।",
              "ta": "📅 *கிடைக்கும் நேரங்கள்*\n{slots}\n\nஸ்லாட் எண்ணை அனுப்புங்கள் (உதா. *2*)."},
    "no_slots": {"en": "Sorry, we're fully booked for the next few days. Reply *HUMAN* and our team will try to fit you in.",
                 "hi": "माफ़ कीजिए, अगले कुछ दिन पूरी तरह बुक हैं। *HUMAN* लिखें, हमारी टीम कोशिश करेगी।",
                 "ta": "மன்னிக்கவும், அடுத்த சில நாட்கள் முழுவதும் புக் ஆகிவிட்டது. *HUMAN* அனுப்புங்கள்."},
    "ask_party": {"en": "How many people? (1–12)", "hi": "कितने लोग? (1–12)", "ta": "எத்தனை பேர்? (1–12)"},
    "booked": {"en": "✅ Table booked for *{n}* on *{when}*. Booking code: *{code}*. See you soon!",
               "hi": "✅ *{n}* लोगों के लिए *{when}* को टेबल बुक हो गई। कोड: *{code}*। जल्द मिलते हैं!",
               "ta": "✅ *{when}* அன்று *{n}* பேருக்கு டேபிள் புக் ஆனது. குறியீடு: *{code}*. சந்திப்போம்!"},
    "bad_choice": {"en": "Please reply with one of the numbers shown.", "hi": "कृपया दिखाए गए नंबरों में से एक भेजें।",
                   "ta": "காட்டப்பட்ட எண்களில் ஒன்றை அனுப்புங்கள்."},
    "ask_lead": {"en": "We'd love to help with that! 🙌 Please share your *name* and *email or phone* so our events team can send a quote.",
                 "hi": "हमें खुशी होगी! 🙌 कृपया अपना *नाम* और *ईमेल या फ़ोन* भेजें ताकि हमारी टीम कोटेशन भेज सके।",
                 "ta": "மகிழ்ச்சியுடன் உதவுகிறோம்! 🙌 உங்கள் *பெயர்* மற்றும் *மின்னஞ்சல் அல்லது தொலைபேசி* அனுப்புங்கள்."},
    "lead_done": {"en": "Thanks {name}! 📝 Our team will contact you at {contact} within 2 working hours.",
                  "hi": "धन्यवाद {name}! 📝 हमारी टीम 2 कार्य-घंटों में {contact} पर संपर्क करेगी।",
                  "ta": "நன்றி {name}! 📝 எங்கள் குழு 2 வேலை நேரத்திற்குள் {contact}-ல் தொடர்புகொள்ளும்."},
    "lead_retry": {"en": "I couldn't spot an email or phone number — could you send it again?",
                   "hi": "मुझे ईमेल या फ़ोन नंबर नहीं मिला — कृपया दोबारा भेजें।",
                   "ta": "மின்னஞ்சல் அல்லது தொலைபேசி எண் கிடைக்கவில்லை — மீண்டும் அனுப்புங்கள்."},
    "handoff": {"en": "I'm connecting you to a member of our team 🙋 — they'll reply here shortly. Sorry for any trouble.",
                "hi": "मैं आपको हमारी टीम से जोड़ रहा हूँ 🙋 — वे जल्द यहीं जवाब देंगे। असुविधा के लिए खेद है।",
                "ta": "உங்களை எங்கள் குழுவுடன் இணைக்கிறேன் 🙋 — விரைவில் இங்கே பதிலளிப்பார்கள். சிரமத்திற்கு வருந்துகிறோம்."},
    "fallback": {"en": "Sorry, I didn't quite get that. Reply *MENU*, *BOOK*, ask about hours/delivery, or *HUMAN* to reach our team.",
                 "hi": "माफ़ कीजिए, समझ नहीं पाया। *MENU*, *BOOK* लिखें, समय/डिलीवरी पूछें, या टीम के लिए *HUMAN*।",
                 "ta": "மன்னிக்கவும், புரியவில்லை. *MENU*, *BOOK*, நேரம்/டெலிவரி பற்றி கேளுங்கள், அல்லது *HUMAN*."},
}
T.update({
    "unknown": {"en": "I'm not sure about that, and I'd rather not guess. 🙏 Reply *HUMAN* and our team will answer you here.",
                "hi": "मुझे इसकी पक्की जानकारी नहीं है, और मैं अंदाज़ा नहीं लगाना चाहता। 🙏 *HUMAN* लिखें, हमारी टीम यहीं जवाब देगी।",
                "ta": "இதைப் பற்றி எனக்கு உறுதியாகத் தெரியவில்லை, ஊகிக்க விரும்பவில்லை. 🙏 *HUMAN* அனுப்புங்கள், எங்கள் குழு பதிலளிக்கும்."},
    "cat_items": {"en": "*{cat}*\n{items}\n\nTap an item to add it, or type e.g. “2 {example}”.",
                  "hi": "*{cat}*\n{items}\n\nजोड़ने के लिए आइटम चुनें, या लिखें जैसे “2 {example}”।",
                  "ta": "*{cat}*\n{items}\n\nசேர்க்க ஒன்றைத் தேர்ந்தெடுங்கள், அல்லது “2 {example}” என்று அனுப்புங்கள்."},
    "voice_off": {"en": "🎤 Got your voice note! Voice replies aren't switched on yet. Could you type your message?",
                  "hi": "🎤 आपका वॉइस नोट मिला! अभी वॉइस सुविधा चालू नहीं है, कृपया संदेश टाइप करें।",
                  "ta": "🎤 உங்கள் குரல் செய்தி கிடைத்தது! குரல் வசதி இன்னும் இயக்கப்படவில்லை, தயவுசெய்து டைப் செய்யுங்கள்."},
    "image_seen": {"en": "📷 From your photo I found:", "hi": "📷 आपकी फ़ोटो में मुझे मिला:", "ta": "📷 உங்கள் புகைப்படத்தில் கண்டது:"},
    "image_handoff": {"en": "📷 Thanks for the photo! A team member will check it and reply here shortly.",
                      "hi": "📷 फ़ोटो के लिए धन्यवाद! हमारी टीम इसे देखकर जल्द यहीं जवाब देगी।",
                      "ta": "📷 புகைப்படத்திற்கு நன்றி! எங்கள் குழு பார்த்து விரைவில் இங்கே பதிலளிக்கும்."},
})
# Button / list labels (WhatsApp limits: button title 20 chars, list row title 24, list button 20)
B = {
    "menu": {"en": "🍛 Menu", "hi": "🍛 मेनू", "ta": "🍛 மெனு"},
    "book": {"en": "📅 Book", "hi": "📅 बुक करें", "ta": "📅 முன்பதிவு"},
    "human": {"en": "🙋 Talk to us", "hi": "🙋 टीम से बात", "ta": "🙋 குழுவுடன் பேச"},
    "confirm": {"en": "✅ Confirm", "hi": "✅ कन्फर्म", "ta": "✅ உறுதி"},
    "more": {"en": "➕ Add more", "hi": "➕ और जोड़ें", "ta": "➕ மேலும்"},
    "cancel": {"en": "✖ Cancel", "hi": "✖ रद्द करें", "ta": "✖ ரத்து"},
    "pickup": {"en": "🏃 Pickup", "hi": "🏃 पिकअप", "ta": "🏃 நேரில் பெற"},
    "view_menu": {"en": "View menu", "hi": "मेनू देखें", "ta": "மெனு பார்க்க"},
    "view_items": {"en": "Choose item", "hi": "आइटम चुनें", "ta": "தேர்வு செய்க"},
    "view_slots": {"en": "Pick a slot", "hi": "स्लॉट चुनें", "ta": "நேரம் தேர்வு"},
}


def buttons(lang, *keys):
    return {"kind": "buttons", "buttons": [{"id": k, "title": B[k][lang]} for k in keys]}


def list_ui(label, section, rows):
    return {"kind": "list", "button": label[:20], "sections": [{"title": section[:24], "rows": rows[:10]}]}


FULFIL = {"pickup": {"en": "pickup", "hi": "पिकअप", "ta": "நேரில் பெறுதல்"}, "delivery": {"en": "delivery", "hi": "डिलीवरी", "ta": "டெலிவரி"}}

KW = {
    "handoff": ["human", "agent", "manager", "staff", "person", "complaint", "refund", "इंसान", "मैनेजर", "शिकायत", "மனிதர்", "மேலாளர்", "புகார்"],
    "cancel": ["cancel", "रद्द", "ரத்து"],
    "confirm": ["confirm", "place order", "checkout", "पक्का", "कन्फर्म", "உறுதி"],
    "cart": ["cart", "कार्ट", "கார்ட்"],
    "menu": ["menu", "मेनू", "மெனு", "what do you have", "क्या मिलेगा"],
    "book": ["book", "booking", "reserve", "reservation", "table", "appointment", "बुक", "टेबल", "முன்பதிவு", "டேபிள்"],
    "lead": ["catering", "bulk", "event", "party order", "corporate", "wedding", "कैटरिंग", "पार्टी", "கேட்டரிங்", "விழா"],
    "greet": ["hi", "hello", "hey", "namaste", "vanakkam", "नमस्ते", "வணக்கம்", "start"],
}
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "ek": 1, "teen": 3, "एक": 1, "दो": 2, "तीन": 3, "चार": 4,
             "ஒன்று": 1, "ஒரு": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(?:\+?\d[\d \-]{8,}\d)")


def has(text: str, words) -> bool:
    t = text.lower()
    for w in words:
        if re.fullmatch(r"[a-z ]+", w):
            if re.search(rf"\b{re.escape(w)}\b", t):
                return True
        elif w in t:
            return True
    return False


def menu_items():
    return [dict(m, aliases=json.loads(m["aliases"])) for m in db.q("SELECT * FROM menu ORDER BY id")]


def parse_items(text: str):
    """Find menu items + quantities in free text (any language)."""
    t = text.lower()
    found = []
    for m in menu_items():
        for a in [m["name"].lower()] + m["aliases"]:
            i = t.find(a.lower())
            if i >= 0:
                before = t[max(0, i - 14):i].split()
                qty = 1
                if before:
                    w = before[-1]
                    qty = int(w) if w.isdigit() else NUM_WORDS.get(w, 1)
                found.append((m, max(1, min(qty, 20))))
                t = t.replace(a.lower(), " ")
                break
    return found


def faq_match(text: str):
    t = text.lower()
    best, score = None, 0
    for f in db.q("SELECT * FROM faq"):
        s = sum(1 for k in f["keywords"].lower().split() if len(k) > 2 and k in t)
        if s > score:
            best, score = f, s
    return best if score >= 1 else None


def available_slots(limit=6):
    return db.q("SELECT * FROM slots WHERE booked < capacity AND starts_at > ? ORDER BY starts_at LIMIT ?",
                (dt.datetime.now().isoformat(timespec="minutes"), limit))


def fmt_slot(s):
    return dt.datetime.fromisoformat(s["starts_at"]).strftime("%a %d %b, %I:%M %p")


def cart_view(cart, lang):
    if not cart:
        return T["cart_empty"][lang]
    lines = "\n".join(f"• {c['qty']} × {c['name']} — ₹{c['qty'] * c['price']}" for c in cart)
    return T["cart"][lang].format(lines=lines, total=sum(c["qty"] * c["price"] for c in cart))


def get_conv(phone, name):
    c = db.q("SELECT * FROM conversations WHERE phone=?", (phone,), one=True)
    if not c:
        db.x("INSERT INTO conversations(phone,name) VALUES(?,?)", (phone, name or phone))
        c = db.q("SELECT * FROM conversations WHERE phone=?", (phone,), one=True)
    return c


def log(conv_id, direction, sender, text, intent=None, lang=None):
    db.x("INSERT INTO messages(conversation_id,direction,sender,text,intent,lang) VALUES(?,?,?,?,?,?)",
         (conv_id, direction, sender, text, intent, lang))
    db.x("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (conv_id,))


def handle_message(phone: str, name: str | None, text: str, action: str | None = None, lang_hint: str | None = None,
                   log_text: str | None = None) -> dict:
    """Process one inbound message.

    action: id of a tapped reply button / list row (e.g. 'slot:12'); lang_hint: language reported by speech-to-text.
    Returns {'reply': str|None, 'intent': str, 'lang': str, 'interactive': dict|None}.
    """
    conv = get_conv(phone, name)
    text = text or ""
    lang = detect_lang(text)
    if lang_hint in LANGS and lang == "en":
        lang = lang_hint
    # keep previous language for taps and short/neutral messages like "2" or "confirm"
    elif action or (lang == "en" and not re.search(r"[a-zA-Z]{4,}", text)):
        lang = conv["lang"] or "en"
    state = db.jload(conv["state"], {}) or {}
    first = name or conv["name"] or ""
    db.x("UPDATE conversations SET lang=?, name=COALESCE(?, name) WHERE id=?", (lang, name, conv["id"]))

    shown = log_text or text
    if conv["needs_human"]:
        log(conv["id"], "in", "customer", shown, "handoff_pending", lang)
        return {"reply": None, "intent": "handoff_pending", "lang": lang, "interactive": None}

    out = route(conv, state, text, lang, first, action)
    intent, reply, ui = (out + (None,))[:3]
    db.x("UPDATE conversations SET state=? WHERE id=?", (json.dumps(state, ensure_ascii=False), conv["id"]))
    log(conv["id"], "in", "customer", shown, intent, lang)
    log(conv["id"], "out", "bot", reply, intent, lang)
    return {"reply": reply, "intent": intent, "lang": lang, "interactive": ui}


def handoff(conv_id, reason):
    db.x("UPDATE conversations SET needs_human=1, handoff_reason=? WHERE id=?", (reason[:200], conv_id))


def handle_image(phone: str, name: str | None, caption: str, found: dict | None) -> dict:
    """A customer photo. found = vision result {'kind': 'prescription'|'product'|..., 'items': [{'name','qty'}], 'summary'}.

    Matched menu items go into the cart; prescriptions, unreadable photos and anything we can't match go to a human."""
    conv = get_conv(phone, name)
    lang = detect_lang(caption) if caption.strip() else (conv["lang"] or "en")
    state = db.jload(conv["state"], {}) or {}
    found = found or {}
    summary = (found.get("summary") or caption or "photo").strip()
    log_text = f"📷 Photo{': ' + caption if caption else ''}"
    if conv["needs_human"]:
        log(conv["id"], "in", "customer", log_text, "handoff_pending", lang)
        return {"reply": None, "intent": "handoff_pending", "lang": lang, "interactive": None}
    wanted = " and ".join(f"{int(i.get('qty') or 1)} {i.get('name', '')}" for i in found.get("items", []) if i.get("name"))
    matched = parse_items(wanted) if wanted else []
    if found.get("kind") == "prescription" or not matched:
        handoff(conv["id"], f"Photo ({found.get('kind') or 'unrecognised'}): {summary}")
        reply, intent, ui = T["image_handoff"][lang], "handoff", None
    else:
        cart = add_to_cart(state, matched)
        reply = T["image_seen"][lang] + "\n" + cart_view(cart, lang)
        intent, ui = "order", buttons(lang, "confirm", "more", "cancel")
    db.x("UPDATE conversations SET state=? WHERE id=?", (json.dumps(state, ensure_ascii=False), conv["id"]))
    log(conv["id"], "in", "customer", log_text, intent, lang)
    log(conv["id"], "out", "bot", reply, intent, lang)
    return {"reply": reply, "intent": intent, "lang": lang, "interactive": ui}


def add_to_cart(state, items):
    cart = state.setdefault("cart", [])
    for m, qty in items:
        for c in cart:
            if c["id"] == m["id"]:
                c["qty"] += qty
                break
        else:
            cart.append({"id": m["id"], "name": m["name"], "price": m["price"], "qty": qty})
    return cart


def business_facts() -> str:
    """Everything the LLM is allowed to know: FAQ answers, menu with prices, open slots."""
    faq = "\n".join(f"- {x['topic']}: {x['answer_en']}" for x in db.q("SELECT * FROM faq"))
    menu = "\n".join(f"- {m['name']} ({m['category']}): ₹{m['price']}" for m in menu_items())
    return f"About us / FAQ:\n{faq}\n\nMenu (only these items exist):\n{menu}"


ACTION_TEXT = {"menu": "menu", "book": "book", "human": "human", "confirm": "confirm", "cancel": "cancel", "pickup": "pickup", "more": "menu"}


def route(conv, state, text, lang, first, action=None):
    flow = state.get("flow")
    t = text.strip()
    if action:
        if action.startswith("cat:"):
            cat = action[4:]
            items = [m for m in menu_items() if m["category"] == cat]
            if items:
                body = T["cat_items"][lang].format(cat=cat, example=items[0]["name"].lower(),
                                                   items="\n".join(f"• {m['name']} — ₹{m['price']}" for m in items))
                rows = [{"id": f"item:{m['id']}", "title": m["name"][:24], "description": f"₹{m['price']}"} for m in items]
                return "menu", body, list_ui(B["view_items"][lang], cat, rows)
        if action.startswith("item:"):
            m = next((m for m in menu_items() if str(m["id"]) == action[5:]), None)
            if m:
                state.pop("flow", None) if flow != "checkout" else None
                return "order", cart_view(add_to_cart(state, [(m, 1)]), lang), buttons(lang, "confirm", "more", "cancel")
        if action.startswith("slot:") and flow == "booking_slot" and action[5:].isdigit() and int(action[5:]) in state.get("slot_options", []):
            state["slot_id"] = int(action[5:])
            state["flow"] = "booking_party"
            return "booking", T["ask_party"][lang]
        t = ACTION_TEXT.get(action, t)

    if has(t, KW["handoff"]):
        state.clear()
        handoff(conv["id"], t)
        return "handoff", T["handoff"][lang]
    if has(t, KW["cancel"]):
        state.clear()
        return "cancel", T["cancelled"][lang], buttons(lang, "menu", "book", "human")

    # --- active flows ---
    if flow == "booking_slot":
        opts = state.get("slot_options", [])
        m = re.search(r"\d+", t)
        if m and 1 <= int(m.group()) <= len(opts):
            state["slot_id"] = opts[int(m.group()) - 1]
            state["flow"] = "booking_party"
            return "booking", T["ask_party"][lang]
        if not has(t, KW["menu"] + KW["book"]):
            return "booking", T["bad_choice"][lang]
    if flow == "booking_party":
        m = re.search(r"\d+", t)
        n = int(m.group()) if m else NUM_WORDS.get(t.lower())
        if n and 1 <= n <= 12:
            slot = db.q("SELECT * FROM slots WHERE id=?", (state["slot_id"],), one=True)
            code = "SR-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
            db.x("UPDATE slots SET booked=booked+1 WHERE id=?", (slot["id"],))
            db.x("INSERT INTO bookings(conversation_id,slot_id,party_size,code) VALUES(?,?,?,?)", (conv["id"], slot["id"], n, code))
            state.clear()
            return "booking", T["booked"][lang].format(n=n, when=fmt_slot(slot), code=code)
        return "booking", T["ask_party"][lang]
    if flow == "checkout" and not (action and action not in ("pickup",)):
        cart = state.get("cart", [])
        pickup = has(t, ["pickup", "pick up", "takeaway", "पिकअप", "நேரில்"])
        fulfil = "pickup" if pickup else "delivery"
        total = sum(c["qty"] * c["price"] for c in cart)
        oid = db.x("INSERT INTO orders(conversation_id,items,total,fulfilment) VALUES(?,?,?,?)",
                   (conv["id"], json.dumps(cart), total, "Pickup" if pickup else f"Delivery: {t[:200]}"))
        state.clear()
        return "order", T["order_done"][lang].format(id=oid, total=total, fulfil=FULFIL[fulfil][lang])
    if flow == "lead":
        em, ph = EMAIL.search(t), PHONE.search(t)
        if em or ph:
            contact = em.group() if em else ph.group()
            lname = re.split(r"[,\n]", t.replace(contact, ""))[0].strip(" -:") or first
            db.x("INSERT INTO leads(conversation_id,name,contact,interest) VALUES(?,?,?,?)",
                 (conv["id"], lname, contact, state.get("interest", "")))
            state.clear()
            return "lead", T["lead_done"][lang].format(name=lname.split()[0] if lname else "", contact=contact)
        return "lead", T["lead_retry"][lang]

    # --- fresh intents ---
    if has(t, KW["lead"]):
        state.update(flow="lead", interest=t[:300])
        return "lead", T["ask_lead"][lang]
    if has(t, KW["confirm"]) and state.get("cart"):
        state["flow"] = "checkout"
        return "order", T["ask_address"][lang], buttons(lang, "pickup", "cancel")
    items = parse_items(t) if not action else []
    if items:
        return "order", cart_view(add_to_cart(state, items), lang), buttons(lang, "confirm", "more", "cancel")
    if has(t, KW["cart"] + KW["confirm"]):
        cart = state.get("cart", [])
        return "order", cart_view(cart, lang), buttons(lang, "confirm", "more", "cancel") if cart else buttons(lang, "menu")
    if has(t, KW["menu"]):
        ms = menu_items()
        items = "\n".join(f"• {m['name']} — ₹{m['price']}" for m in ms)
        cats = list(dict.fromkeys(m["category"] for m in ms))
        rows = [{"id": f"cat:{c}", "title": c[:24], "description": f"{sum(m['category'] == c for m in ms)} items"} for c in cats]
        return "menu", T["menu"][lang].format(items=items), list_ui(B["view_menu"][lang], "Categories", rows)
    if has(t, KW["book"]):
        slots = available_slots()
        if not slots:
            return "booking", T["no_slots"][lang]
        state.update(flow="booking_slot", slot_options=[s["id"] for s in slots])
        rows = [{"id": f"slot:{s['id']}", "title": fmt_slot(s)[:24], "description": f"{s['capacity'] - s['booked']} left"} for s in slots]
        return ("booking", T["slots"][lang].format(slots="\n".join(f"*{i+1}.* {fmt_slot(s)}" for i, s in enumerate(slots))),
                list_ui(B["view_slots"][lang], "Available", rows))
    f = faq_match(t)
    if f:
        ans = f[f"answer_{lang}"]
        return "faq", ans
    if has(t, KW["greet"]):
        return "greeting", T["greet"][lang].format(name=first.split()[0] if first else ""), buttons(lang, "menu", "book", "human")
    if llm.enabled() and t:
        out = llm.grounded_answer("Spice Route Kitchen, a Chennai restaurant", business_facts(), t, lang)
        if out == llm.UNKNOWN:
            return "llm_unknown", T["unknown"][lang], buttons(lang, "human", "menu")
        if out:
            return "llm", out
    return "fallback", T["fallback"][lang], buttons(lang, "menu", "book", "human")
