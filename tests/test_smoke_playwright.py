"""Browser smoke test: chat in the phone mockup, then check the owner dashboard."""
import pytest
from playwright.sync_api import sync_playwright, expect


@pytest.mark.e2e
def test_smoke(live_server):
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.goto(live_server)
        page.get_by_test_id("chat-input").fill("Menu")
        page.get_by_test_id("chat-send").click()
        expect(page.get_by_test_id("chat")).to_contain_text("Paneer Tikka")
        page.get_by_test_id("wa-list").get_by_role("button").first.click()  # WhatsApp list message
        page.get_by_test_id("row-cat:Drinks").click()
        expect(page.get_by_test_id("chat")).to_contain_text("Tap an item")
        page.get_by_test_id("wa-list").get_by_role("button").first.click()
        page.get_by_test_id("row-item:5").click()
        expect(page.get_by_test_id("btn-confirm")).to_be_visible()  # reply buttons
        page.get_by_test_id("chat-input").fill("2 masala dosa")
        page.get_by_test_id("chat-voice").click()
        expect(page.get_by_test_id("chat")).to_contain_text("Voice note")
        page.get_by_test_id("persona-Lakshmi").click()
        page.get_by_test_id("chat-input").fill("வணக்கம்")
        page.get_by_test_id("chat-send").click()
        expect(page.get_by_test_id("ai-insight")).to_contain_text("Tamil")
        page.get_by_test_id("tab-dash").click()
        page.get_by_test_id("login-user").fill("admin")
        page.get_by_test_id("login-pass").fill("cyberfield")
        page.get_by_test_id("login-submit").click()
        expect(page.get_by_test_id("stats")).to_contain_text("Revenue")
        page.get_by_test_id("dash-Broadcasts").click()
        expect(page.get_by_test_id("broadcast").first).to_contain_text("pending approval")
        page.get_by_test_id("dash-Analytics").click()
        expect(page.get_by_test_id("analytics")).to_contain_text("Busy hours")
        expect(page.locator(".recharts-bar-rectangle").first).to_be_visible()
        page.get_by_test_id("dash-Settings").click()
        expect(page.get_by_test_id("settings-faq")).to_contain_text("Topic")
        # switch tenant: the clinic has its own data and wording
        page.get_by_test_id("biz-select").select_option(label="Sunrise Family Clinic")
        page.get_by_test_id("dash-Settings").click()
        expect(page.get_by_test_id("biz-name")).to_have_value("Sunrise Family Clinic")
        page.get_by_test_id("tab-sim").click()
        page.get_by_test_id("chat-input").fill("Services")
        page.get_by_test_id("chat-send").click()
        expect(page.get_by_test_id("chat")).to_contain_text("Blood test")
        b.close()
