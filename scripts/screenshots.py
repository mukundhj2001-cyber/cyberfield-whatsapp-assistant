"""Capture README screenshots into docs/screenshots. Usage: python scripts/screenshots.py (builds nothing; needs frontend/dist)."""
import os, subprocess, sys, tempfile, time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"; OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, "DB_PATH": str(Path(tempfile.mkdtemp()) / "shots.db")}
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8811"], cwd=ROOT / "backend", env=env)
URL = "http://127.0.0.1:8811"
for _ in range(60):
    try: httpx.get(URL + "/api/health"); break
    except Exception: time.sleep(0.25)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg.goto(URL)
        def say(t):
            n = pg.locator("[data-testid=chat] > div").count()
            pg.get_by_test_id("chat-input").fill(t); pg.get_by_test_id("chat-send").click()
            pg.wait_for_function(f"document.querySelectorAll('[data-testid=chat] > div').length >= {n + 2}")
        for t in ["Hi", "2 masala dosa and 2 filter coffee", "confirm"]: say(t)
        pg.wait_for_timeout(600); pg.screenshot(path=OUT / "01-chat-order-english.png")
        pg.get_by_test_id("persona-Vikram").click()
        for t in ["नमस्ते", "टेबल बुक करना है", "2"]: say(t)
        pg.wait_for_timeout(600); pg.screenshot(path=OUT / "02-chat-booking-hindi.png")
        pg.get_by_test_id("persona-Lakshmi").click()
        for t in ["வணக்கம்", "டெலிவரி இருக்கா?"]: say(t)
        pg.wait_for_timeout(600); pg.screenshot(path=OUT / "03-chat-faq-tamil.png")
        pg.get_by_test_id("tab-dash").click(); pg.wait_for_timeout(800)
        pg.locator("tbody tr").first.click(); pg.wait_for_timeout(600)
        pg.screenshot(path=OUT / "04-dashboard-conversations.png", full_page=True)
        for i, tab in enumerate(["Orders", "Bookings", "Leads", "Handoff queue", "Broadcasts"], 5):
            pg.get_by_test_id(f"dash-{tab}").click(); pg.wait_for_timeout(500)
            if tab == "Handoff queue": pg.locator("tbody tr").first.click(); pg.wait_for_timeout(500)
            pg.screenshot(path=OUT / f"0{i}-dashboard-{tab.lower().replace(' ', '-')}.png", full_page=True)
        b.close()
finally:
    srv.terminate()
print("saved to", OUT)
