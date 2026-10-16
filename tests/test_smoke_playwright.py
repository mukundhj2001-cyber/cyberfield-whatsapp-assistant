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
        b.close()
