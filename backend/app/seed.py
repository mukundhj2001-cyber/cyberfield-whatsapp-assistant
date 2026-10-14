"""Seed demo business: Spice Route Kitchen (restaurant + table reservations)."""
import datetime as dt, json
from . import db

BUSINESS = {"name": "Spice Route Kitchen", "type": "Restaurant · Chennai", "phone": "+91 98400 00000"}

MENU = [
    ("Paneer Tikka", 249, "Starters", ["paneer", "पनीर", "பனீர்"]),
    ("Butter Chicken", 329, "Mains", ["butter chicken", "chicken", "चिकन", "சிக்கன்"]),
    ("Masala Dosa", 149, "South Indian", ["dosa", "डोसा", "தோசை"]),
    ("Veg Biryani", 229, "Mains", ["biryani", "बिरयानी", "பிரியாணி"]),
    ("Mango Lassi", 99, "Drinks", ["lassi", "लस्सी", "லஸ்ஸி"]),
    ("Filter Coffee", 59, "Drinks", ["coffee", "कॉफी", "காபி"]),
]

FAQ = [
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
]


def seed(force: bool = False):
    db.init()
    if db.q("SELECT COUNT(*) c FROM menu", one=True)["c"] and not force:
        return
    for t in ["conversations", "messages", "menu", "orders", "slots", "bookings", "leads", "faq", "broadcasts", "outbox"]:
        db.x(f"DELETE FROM {t}")
    for n, p, c, a in MENU:
        db.x("INSERT INTO menu(name,price,category,aliases) VALUES(?,?,?,?)", (n, p, c, json.dumps(a)))
    for f in FAQ:
        db.x("INSERT INTO faq(topic,keywords,answer_en,answer_hi,answer_ta) VALUES(?,?,?,?,?)", f)
    today = dt.date.today()
    for d in range(1, 4):
        for h in (13, 15, 19, 20, 21):
            db.x("INSERT INTO slots(starts_at,capacity) VALUES(?,?)",
                 (dt.datetime.combine(today + dt.timedelta(days=d), dt.time(h, 0)).isoformat(timespec="minutes"), 2))
    # Sample history so the dashboard isn't empty on first run
    from .engine import handle_message
    demo = [
        ("+919840011111", "Priya", ["Hi", "2 paneer tikka and 1 mango lassi", "confirm", "12 Lake View Road, Mylapore"]),
        ("+919840022222", "Rahul", ["नमस्ते, आप कितने बजे खुलते हैं?", "टेबल बुक करना है", "2", "4"]),
        ("+919840033333", "Karthik", ["வணக்கம், டெலிவரி இருக்கா?", "catering for 80 people at our office", "Karthik Raman, karthik@acmecorp.in"]),
        ("+919840044444", "Meera", ["My last order was cold, I want to talk to a manager"]),
    ]
    for phone, name, texts in demo:
        for t in texts:
            handle_message(phone, name, t)
    db.x("INSERT INTO broadcasts(title,body,audience) VALUES(?,?,?)",
         ("Diwali special", "🪔 Happy Diwali from Spice Route Kitchen! Get 15% off all orders this weekend — just reply MENU to order.", "all"))
