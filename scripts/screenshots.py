"""Capture README screenshots into docs/screenshots. Usage: python scripts/screenshots.py (needs frontend/dist built)."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"; OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.glob("*.png"):
    old.unlink()
env = {k: v for k, v in os.environ.items() if not k.startswith(("WHATSAPP_", "LLM_", "STT_", "RAZORPAY_", "ADMIN_"))}
env["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "shots.db")
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8811"], cwd=ROOT / "backend", env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
URL = "http://127.0.0.1:8811"
for _ in range(60):
    try: httpx.get(URL + "/api/health"); break
    except Exception: time.sleep(0.25)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg.goto(URL)
        def n_msgs(): return pg.locator("[data-testid=chat] > div").count()
        def wait_reply(n): pg.wait_for_function(f"document.querySelectorAll('[data-testid=chat] > div').length >= {n + 2}")
        def say(t, how="chat-send"):
            n = n_msgs(); pg.get_by_test_id("chat-input").fill(t); pg.get_by_test_id(how).click(); wait_reply(n)
        def tap(testid):
            n = n_msgs(); pg.get_by_test_id(testid).click(); wait_reply(n)
        def open_list(): pg.get_by_test_id("wa-list").get_by_role("button").first.click(); pg.wait_for_timeout(200)
        def shot(name, full=False): pg.wait_for_timeout(500); pg.screenshot(path=OUT / f"{name}.png", full_page=full)

        say("Hi"); say("Menu"); open_list(); shot("01-chat-menu-list")
        tap("row-cat:South Indian"); open_list(); tap("row-item:3"); shot("02-chat-cart-buttons")
        tap("btn-confirm"); tap("btn-pickup"); shot("03-chat-order-payment-link")
        pg.get_by_test_id("persona-Vikram").click()
        say("नमस्ते"); say("टेबल बुक करना है"); open_list(); shot("04-chat-booking-hindi")
        pg.get_by_test_id("persona-Lakshmi").click()
        say("வணக்கம், டெலிவரி இருக்கா?"); say("2 தோசை 1 காபி", "chat-voice"); shot("05-chat-voice-tamil")
        pg.get_by_test_id("persona-Ananya").click()
        say("photo of 2 butter chicken and 1 mango lassi", "chat-photo"); shot("06-chat-photo-to-cart")

        pg.get_by_test_id("tab-dash").click(); pg.wait_for_timeout(400); shot("07-login")
        pg.get_by_test_id("login-user").fill("admin"); pg.get_by_test_id("login-pass").fill("cyberfield")
        pg.get_by_test_id("login-submit").click(); pg.wait_for_timeout(800)
        pg.locator("tbody tr").first.click(); shot("08-dashboard-conversations", True)
        for i, tab in enumerate(["Orders", "Bookings", "Handoff queue", "Broadcasts", "Analytics", "Settings"], 9):
            pg.get_by_test_id(f"dash-{tab}").click(); pg.wait_for_timeout(700)
            if tab == "Handoff queue": pg.locator("tbody tr").first.click()
            if tab == "Analytics": pg.wait_for_timeout(800)
            shot(f"{i:02d}-dashboard-{tab.lower().replace(' ', '-')}", tab in ("Handoff queue", "Broadcasts", "Analytics"))
        pg.get_by_test_id("biz-select").select_option(label="Sunrise Family Clinic"); pg.wait_for_timeout(500)
        pg.get_by_test_id("tab-sim").click()
        say("Hi"); say("I need a blood test"); open_list(); shot("15-clinic-tenant-booking")
        b.close()
finally:
    srv.terminate()
print("saved to", OUT)
