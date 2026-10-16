"""Demo businesses: Spice Route Kitchen (restaurant), Sunrise Family Clinic (clinic), Glow Studio (salon). All fictional."""
import datetime as dt, json, random
from . import db

# Fresh installs only. Replace with the business's real UPI ID in Settings before going live.
RESTAURANT = {
    "slug": "spice-route", "name": "Spice Route Kitchen", "kind": "restaurant", "tagline": "Restaurant · Chennai", "code_prefix": "SR",
    "upi_id": "spiceroute.demo@upi", "orders_enabled": 1, "languages": ["en", "hi", "ta"], "default_lang": "en",
    "hours": {"en": "Every day 11:00 AM – 11:00 PM (kitchen closes 10:30 PM)", "hi": "रोज़ सुबह 11 बजे से रात 11 बजे तक",
              "ta": "தினமும் காலை 11 மணி முதல் இரவு 11 மணி வரை"},
    "slot_hours": (13, 15, 19, 20, 21), "slot_capacity": 2,
    "menu": [
        ("Paneer Tikka", 249, "Starters", ["paneer", "पनीर", "பனீர்"]),
        ("Butter Chicken", 329, "Mains", ["butter chicken", "chicken", "चिकन", "சிக்கன்"]),
        ("Masala Dosa", 149, "South Indian", ["dosa", "डोसा", "தோசை"]),
        ("Veg Biryani", 229, "Mains", ["biryani", "बिरयानी", "பிரியாணி"]),
        ("Mango Lassi", 99, "Drinks", ["lassi", "लस्सी", "லஸ்ஸி"]),
        ("Filter Coffee", 59, "Drinks", ["coffee", "कॉफी", "காபி"]),
    ],
    "faq": [
        ("Opening hours", "hours timing open close time समय खुला खुलते बजे टाइम நேரம் திறந்து",
         "We're open every day 11:00 AM – 11:00 PM. Kitchen closes at 10:30 PM.",
         "हम रोज़ सुबह 11 बजे से रात 11 बजे तक खुले हैं। किचन रात 10:30 बजे बंद होता है।",
         "நாங்கள் தினமும் காலை 11 மணி முதல் இரவு 11 மணி வரை திறந்திருக்கிறோம். சமையலறை இரவு 10:30க்கு மூடப்படும்."),
        ("Location", "location address where located पता कहाँ முகவரி எங்கே",
         "We're at 12 Cathedral Road, Gopalapuram, Chennai 600086 (opposite the park). Google Maps: search 'Spice Route Kitchen'.",
         "हमारा पता: 12 कैथेड्रल रोड, गोपालपुरम, चेन्नई 600086 (पार्क के सामने)।",
         "எங்கள் முகவரி: 12 கதீட்ரல் சாலை, கோபாலபுரம், சென்னை 600086 (பூங்கா எதிரில்)."),
        ("Delivery", "delivery deliver home doorstep डिलीवरी घर டெலிவரி வீட்டுக்கு",
         "We deliver within 5 km. Free delivery above ₹499, otherwise ₹40. Typical time: 35–45 minutes.",
         "हम 5 किमी तक डिलीवरी करते हैं। ₹499 से ऊपर मुफ़्त, वरना ₹40। समय: 35–45 मिनट।",
         "5 கி.மீ. வரை டெலிவரி செய்கிறோம். ₹499க்கு மேல் இலவசம், இல்லையெனில் ₹40. நேரம்: 35–45 நிமிடம்."),
        ("Payments", "payment pay upi card cash gpay भुगतान पेमेंट பணம் கட்டணம்",
         "We accept UPI, all major cards and cash. Pay on delivery is available.",
         "हम UPI, सभी प्रमुख कार्ड और कैश लेते हैं। डिलीवरी पर भुगतान भी उपलब्ध है।",
         "UPI, கார்டுகள் மற்றும் பணம் ஏற்கிறோம். டெலிவரியின் போது பணம் செலுத்தலாம்."),
        ("Vegetarian & Jain", "veg vegetarian vegan jain शाकाहारी जैन சைவ",
         "Over half our menu is vegetarian, and we can prepare Jain versions of most veg dishes on request.",
         "हमारा आधे से ज़्यादा मेनू शाकाहारी है, और ज़्यादातर व्यंजन जैन तरीके से भी बन सकते हैं।",
         "எங்கள் மெனுவில் பாதிக்கு மேல் சைவ உணவுகள்; கோரிக்கையின் பேரில் ஜெயின் உணவும் தயாரிப்போம்."),
        ("Parking", "parking valet पार्किंग பார்க்கிங்",
         "Free valet parking is available for dine-in guests after 6 PM.",
         "शाम 6 बजे के बाद डाइन-इन मेहमानों के लिए मुफ़्त वैले पार्किंग है।",
         "மாலை 6 மணிக்குப் பிறகு உணவருந்த வருபவர்களுக்கு இலவச வேலட் பார்க்கிங் உள்ளது."),
    ],
    "templates": [("booking_reminder", "en", "UTILITY", "reminder", "Hi {{1}}, a reminder of your booking at Spice Route Kitchen on {{2}}. Code: {{3}}.", 3),
                  ("weekend_offer", "en", "MARKETING", "offer", "Hi {{1}}! 🪔 15% off all orders this weekend at Spice Route Kitchen. Reply MENU to order.", 1)],
    "demo": [
        ("+919840011111", "Priya", ["Hi", "2 paneer tikka and 1 mango lassi", "confirm", "12 Lake View Road, Mylapore"]),
        ("+919840022222", "Rahul", ["नमस्ते, आप कितने बजे खुलते हैं?", "टेबल बुक करना है", "2", "4"]),
        ("+919840033333", "Karthik", ["வணக்கம், டெலிவரி இருக்கா?", "catering for 80 people at our office", "Karthik Raman, karthik@acmecorp.in"]),
        ("+919840044444", "Meera", ["My last order was cold, I want to talk to a manager"]),
    ],
    "broadcast": ("Diwali special", "🪔 Happy Diwali from Spice Route Kitchen! Get 15% off all orders this weekend — just reply MENU to order."),
}

CLINIC = {
    "slug": "sunrise-clinic", "name": "Sunrise Family Clinic", "kind": "clinic", "tagline": "Clinic · Anna Nagar, Chennai", "code_prefix": "SC",
    "upi_id": "", "orders_enabled": 0, "languages": ["en", "hi", "ta"], "default_lang": "en",
    "hours": {"en": "Mon–Sat 9:00 AM – 1:00 PM and 5:00 PM – 9:00 PM. Sunday closed.", "hi": "सोम–शनि सुबह 9 से 1 और शाम 5 से 9 बजे। रविवार बंद।",
              "ta": "திங்கள்–சனி காலை 9 – மதியம் 1, மாலை 5 – இரவு 9. ஞாயிறு விடுமுறை."},
    "slot_hours": (10, 11, 12, 17, 18, 19), "slot_capacity": 1,
    "menu": [
        ("General consultation", 500, "Consultations", ["consultation", "doctor", "checkup with doctor", "डॉक्टर", "மருத்துவர்"]),
        ("Child specialist", 700, "Consultations", ["paediatric", "pediatric", "child", "kids doctor", "बच्चों", "குழந்தை"]),
        ("Blood test (CBC)", 350, "Lab tests", ["blood test", "cbc", "खून जांच", "இரத்த பரிசோதனை"]),
        ("Full body checkup", 1999, "Lab tests", ["full body", "health checkup", "हेल्थ चेकअप", "முழு உடல்"]),
        ("Dental cleaning", 900, "Dental", ["dental", "teeth cleaning", "दांत", "பல்"]),
    ],
    "faq": [
        ("Location", "location address where located पता कहाँ முகவரி எங்கே",
         "We're at 4th Avenue, Anna Nagar East, Chennai 600102, above Apollo Pharmacy.",
         "हमारा पता: 4th एवेन्यू, अन्ना नगर ईस्ट, चेन्नई 600102 (अपोलो फार्मेसी के ऊपर)।",
         "எங்கள் முகவரி: 4வது அவென்யூ, அண்ணா நகர் கிழக்கு, சென்னை 600102 (அப்பல்லோ பார்மசி மேலே)."),
        ("Insurance", "insurance cashless claim बीमा காப்பீடு",
         "We give itemised bills for insurance claims. Cashless is not available at the clinic.",
         "बीमा क्लेम के लिए हम पूरा बिल देते हैं। क्लिनिक में कैशलेस सुविधा नहीं है।",
         "காப்பீட்டு கோரிக்கைக்கு விரிவான பில் தருகிறோம். கேஷ்லெஸ் வசதி இல்லை."),
        ("Reports", "report reports results रिपोर्ट அறிக்கை",
         "Blood test reports are ready the same evening and are sent to you on WhatsApp as a PDF.",
         "ब्लड टेस्ट रिपोर्ट उसी शाम तैयार होती है और WhatsApp पर PDF भेजी जाती है।",
         "இரத்த பரிசோதனை அறிக்கை அதே மாலை தயாராகி WhatsApp-ல் PDF ஆக அனுப்பப்படும்."),
        ("Emergency", "emergency urgent ambulance आपातकाल அவசரம்",
         "For a medical emergency, please call 108 or go to the nearest hospital. This chat is not monitored 24/7.",
         "आपात स्थिति में कृपया 108 पर कॉल करें या नज़दीकी अस्पताल जाएँ। यह चैट 24/7 नहीं देखी जाती।",
         "அவசரத்திற்கு 108-ஐ அழையுங்கள் அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லுங்கள்."),
    ],
    "templates": [("appointment_reminder", "en", "UTILITY", "reminder", "Hi {{1}}, a reminder of your appointment at Sunrise Family Clinic on {{2}}. Code: {{3}}.", 3)],
    "demo": [
        ("+919840055555", "Anitha", ["Hi", "I need a blood test", "1"]),
        ("+919840066666", "Suresh", ["Do you accept insurance?"]),
    ],
    "broadcast": None,
}

SALON = {
    "slug": "glow-studio", "name": "Glow Studio Salon", "kind": "salon", "tagline": "Salon · Velachery, Chennai", "code_prefix": "GS",
    "upi_id": "glowstudio.demo@upi", "orders_enabled": 0, "languages": ["en", "ta"], "default_lang": "en",
    "hours": {"en": "Tue–Sun 10:00 AM – 8:30 PM. Monday closed.", "ta": "செவ்வாய்–ஞாயிறு காலை 10 – இரவு 8:30. திங்கள் விடுமுறை."},
    "slot_hours": (11, 13, 16, 18), "slot_capacity": 2,
    "menu": [
        ("Haircut", 399, "Hair", ["haircut", "hair cut", "trim", "முடி வெட்டு"]),
        ("Hair spa", 999, "Hair", ["hair spa", "spa"]),
        ("Facial", 1299, "Skin", ["facial", "ஃபேஷியல்"]),
        ("Manicure", 499, "Hands & feet", ["manicure", "nails"]),
        ("Bridal makeup", 14999, "Bridal", ["bridal", "makeup", "மேக்கப்"]),
    ],
    "faq": [
        ("Location", "location address where located முகவரி எங்கே",
         "We're at 22 Taramani Link Road, Velachery, Chennai 600042, next to Phoenix Mall gate 3.", "",
         "எங்கள் முகவரி: 22 தரமணி லிங்க் சாலை, வேளச்சேரி, சென்னை 600042 (ஃபீனிக்ஸ் மால் கேட் 3 அருகில்)."),
        ("Walk-ins", "walk walkin walk-in without appointment",
         "Walk-ins are welcome on weekdays. On weekends we recommend booking — reply BOOK.", "",
         "வார நாட்களில் நேரடியாக வரலாம். வார இறுதியில் முன்பதிவு செய்யுங்கள் — BOOK அனுப்புங்கள்."),
        ("Products", "products brand brands loreal organic",
         "We use L'Oréal Professionnel and organic products for skin treatments. Patch tests are free.", "",
         "L'Oréal Professionnel மற்றும் இயற்கை பொருட்களைப் பயன்படுத்துகிறோம். பேட்ச் டெஸ்ட் இலவசம்."),
    ],
    "templates": [("appointment_reminder", "en", "UTILITY", "reminder", "Hi {{1}}, see you at Glow Studio on {{2}}. Code: {{3}}.", 3)],
    "demo": [("+919840077777", "Divya", ["Hi", "bridal makeup for my wedding in December", "Divya, divya.k@example.com"])],
    "broadcast": ("Monsoon hair spa", "☔ Monsoon offer at Glow Studio: hair spa at ₹799 all week. Reply BOOK to grab a slot."),
}

BUSINESSES = [RESTAURANT, CLINIC, SALON]
BUSINESS = {"name": RESTAURANT["name"], "type": RESTAURANT["tagline"], "phone": "+91 98400 00000"}  # v1 compat
TABLES = ["conversations", "messages", "menu", "orders", "slots", "bookings", "leads", "faq", "broadcasts", "outbox",
          "templates", "message_status", "processed_messages", "businesses"]


def _insert_business(b, bid=None, upi=None):
    cols = {"slug": b["slug"], "name": b["name"], "kind": b["kind"], "tagline": b["tagline"], "code_prefix": b["code_prefix"],
            "upi_id": b["upi_id"] if upi is None else upi, "orders_enabled": b["orders_enabled"],
            "languages": json.dumps(b["languages"]), "default_lang": b["default_lang"], "hours": json.dumps(b["hours"], ensure_ascii=False)}
    if bid:
        cols["id"] = bid
    return db.x(f"INSERT INTO businesses({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(cols.values()))


def _fill(b, bid):
    for n, p, c, a in b["menu"]:
        db.x("INSERT INTO menu(business_id,name,price,category,aliases) VALUES(?,?,?,?,?)", (bid, n, p, c, json.dumps(a, ensure_ascii=False)))
    for f in b["faq"]:
        db.x("INSERT INTO faq(business_id,topic,keywords,answer_en,answer_hi,answer_ta) VALUES(?,?,?,?,?,?)", (bid, *f))
    add_slots(bid, days=3, hours=b["slot_hours"], capacity=b["slot_capacity"])
    for t in b["templates"]:
        db.x("INSERT INTO templates(business_id,name,language,category,purpose,body,param_count) VALUES(?,?,?,?,?,?,?)", (bid, *t))


def add_slots(bid, days=3, hours=(13, 19), capacity=1, start=1):
    today = dt.date.today()
    n = 0
    for d in range(start, start + days):
        for h in hours:
            at = dt.datetime.combine(today + dt.timedelta(days=d), dt.time(int(h), 0)).isoformat(timespec="minutes")
            if not db.q("SELECT 1 FROM slots WHERE business_id=? AND starts_at=?", (bid, at), one=True):
                db.x("INSERT INTO slots(business_id,starts_at,capacity) VALUES(?,?,?)", (bid, at, capacity))
                n += 1
    return n


HISTORY_NAMES = ["Arjun", "Fathima", "Gokul", "Harini", "Imran", "Janani", "Kavya", "Lokesh", "Nisha", "Pradeep", "Revathi", "Sanjay"]
HISTORY_INTENTS = ["faq", "menu", "order", "booking", "greeting", "faq", "fallback", "lead"]
BUSY = [11, 12, 13, 13, 14, 18, 19, 19, 20, 20, 20, 21, 21, 22]


def _history(bid, b, scale=1):
    """Two weeks of fictional past chats so the analytics page has shape. Numbers use the reserved +91 98400 9xxxx range."""
    from .admin import _offset_minutes
    rng = random.Random(bid * 7)
    off = dt.timedelta(minutes=_offset_minutes())
    now_local = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + off
    menu = db.q("SELECT * FROM menu WHERE business_id=?", (bid,))
    for day in range(1, 14):
        for _ in range(rng.randint(1, 3) * scale):
            local = dt.datetime.combine((now_local - dt.timedelta(days=day)).date(), dt.time(rng.choice(BUSY), rng.randint(0, 59)))
            at = (local - off).strftime("%Y-%m-%d %H:%M:%S")
            phone = f"+9198400{9 * 10000 + rng.randint(0, 9999):05d}"
            if db.q("SELECT 1 FROM conversations WHERE business_id=? AND phone=?", (bid, phone), one=True):
                continue
            cid = db.x("INSERT INTO conversations(business_id,phone,name,lang,updated_at) VALUES(?,?,?,?,?)",
                       (bid, phone, rng.choice(HISTORY_NAMES), rng.choice(b["languages"]), at))
            for _ in range(rng.randint(1, 3)):
                db.x("INSERT INTO messages(conversation_id,direction,sender,text,intent,lang,created_at) VALUES(?,?,?,?,?,?,?)",
                     (cid, "in", "customer", "(earlier chat)", rng.choice(HISTORY_INTENTS), "en", at))
            if b["orders_enabled"] and menu and rng.random() < 0.35:
                m = rng.choice(menu); q = rng.randint(1, 3)
                db.x("INSERT INTO orders(business_id,conversation_id,items,total,fulfilment,status,payment_status,created_at) VALUES(?,?,?,?,?,?,?,?)",
                     (bid, cid, json.dumps([{"id": m["id"], "name": m["name"], "price": m["price"], "qty": q}]), m["price"] * q,
                      "Pickup", "completed", rng.choice(["paid", "unpaid"]), at))


def seed(force: bool = False):
    db.init()
    if force:
        for t in TABLES:
            db.x(f"DELETE FROM {t}")
    from . import tenants
    from .engine import handle_message
    upgraded = not force and db.q("SELECT COUNT(*) c FROM menu", one=True)["c"] > 0 and not db.q("SELECT 1 FROM businesses LIMIT 1", one=True)
    if upgraded:
        # v1 single-business database: its data becomes business #1. No demo UPI ID on a live install.
        _insert_business(RESTAURANT, bid=1, upi="")
        for t in RESTAURANT["templates"]:
            db.x("INSERT INTO templates(business_id,name,language,category,purpose,body,param_count) VALUES(1,?,?,?,?,?,?)", t)
    for b in BUSINESSES:
        if db.q("SELECT 1 FROM businesses WHERE slug=?", (b["slug"],), one=True):
            continue
        bid = _insert_business(b)
        _fill(b, bid)
        biz = tenants.get(bid)
        for phone, name, texts in b["demo"]:
            for t in texts:
                handle_message(phone, name, t, biz=biz)
        _history(bid, b, scale=1)
        if b["broadcast"]:
            db.x("INSERT INTO broadcasts(business_id,title,body,audience) VALUES(?,?,?,?)", (bid, *b["broadcast"], "all"))
