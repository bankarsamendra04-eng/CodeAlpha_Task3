import os
import sys
import asyncio
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"

async def run_tests():
    print("==================================================")
    print("STARTING E2E STARTUP AUTHENTICATION FLOW TESTS")
    print("==================================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # TEST 1: Fresh unauthenticated startup lands on Login page
        print("\n[TEST 1] Visiting fresh application (no localStorage)...")
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=8000)
        card_title = await page.inner_text(".auth-card-title")
        print(f"  [PASS] Gatekeeper rendered: '{card_title}'")
        assert "Welcome to AI Music Studio" in card_title

        studio_card = await page.query_selector(".studio-card")
        assert studio_card is None, "Studio card must NOT be visible to unauthenticated user!"
        print("  [PASS] Protected studio controls are hidden.")

        # TEST 2: Invalid credentials display human-readable error
        print("\n[TEST 2] Testing invalid credentials submission...")
        inputs = await page.query_selector_all(".auth-input")
        await inputs[0].fill("nonexistent_user")
        await inputs[1].fill("WrongPassword123!")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".auth-error", timeout=5000)
        error_text = await page.inner_text(".auth-error")
        print(f"  [PASS] Error displayed: '{error_text}'")
        assert "[object Object]" not in error_text
        assert "Invalid username or password" in error_text

        # TEST 3: Authenticate as regular USER
        print("\n[TEST 3] Logging in with standard USER account ('user')...")
        await inputs[0].fill("user")
        await inputs[1].fill("UserPass123!")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".studio-card", timeout=8000)
        print("  [PASS] Successfully entered Studio Dashboard!")

        user_greeting = await page.inner_text(".user-greeting")
        print(f"  [PASS] User widget displays: '{user_greeting.strip()}'")
        assert "user" in user_greeting

        admin_nav_btn = await page.query_selector(".btn-admin-nav")
        assert admin_nav_btn is None, "Regular USER must NOT have Admin nav button!"
        print("  [PASS] Admin button correctly hidden from USER.")

        # TEST 4: Browser Refresh preserves session
        print("\n[TEST 4] Refreshing browser with active session...")
        await page.reload()
        await page.wait_for_selector(".studio-card", timeout=8000)
        refreshed_greeting = await page.inner_text(".user-greeting")
        print(f"  [PASS] Active session preserved after refresh: '{refreshed_greeting.strip()}'")
        assert "user" in refreshed_greeting

        # TEST 5: User Logout
        print("\n[TEST 5] Testing User Logout...")
        logout_btn = await page.query_selector("button:text('Logout')")
        assert logout_btn is not None
        await logout_btn.click()

        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("  [PASS] Logout redirected immediately to standalone Login screen.")

        token_in_storage = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        user_in_storage = await page.evaluate("() => localStorage.getItem('aimusic_user')")
        assert token_in_storage is None
        assert user_in_storage is None
        print("  [PASS] localStorage tokens and user profile securely cleared.")

        # TEST 6: Unauthenticated user cannot access dashboard via URL navigation
        print("\n[TEST 6] Testing direct protected URL navigation without session...")
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        unauth_card = await page.inner_text(".auth-card-title")
        print(f"  [PASS] Direct navigation without session intercepted: '{unauth_card}'")
        assert "Welcome to AI Music Studio" in unauth_card

        # TEST 7: Expired or Corrupted Token handling on startup
        print("\n[TEST 7] Testing invalid/corrupted token in localStorage on reload...")
        await page.evaluate("() => { localStorage.setItem('aimusic_token', 'malformed.fake.jwt'); localStorage.setItem('aimusic_user', JSON.stringify({username:'hacker', role:'ADMIN'})); }")
        await page.reload()
        await page.wait_for_selector(".auth-card-standalone", timeout=8000)
        card_title_invalid = await page.inner_text(".auth-card-title")
        print(f"  [PASS] Invalid session purged, gated back to: '{card_title_invalid}'")
        cleaned_token = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        assert cleaned_token is None, "Corrupted token was not removed from localStorage!"
        print("  [PASS] Corrupted session cleared by backend verification check.")

        # TEST 8: Admin Login & Protected Admin Dashboard
        print("\n[TEST 8] Logging in with ADMIN account ('samendra_bankar')...")
        admin_inputs = await page.query_selector_all(".auth-input")
        await admin_inputs[0].fill("samendra_bankar")
        await admin_inputs[1].fill("Samm@2004")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".admin-container", timeout=8000)
        admin_title = await page.inner_text(".admin-title")
        print(f"  [PASS] Landed on: '{admin_title.encode('ascii', 'ignore').decode()}'")
        assert "Admin Dashboard" in admin_title

        kpis = await page.query_selector_all(".kpi-card")
        print(f"  [PASS] Verified {len(kpis)} live telemetry KPI cards rendered on Admin Dashboard.")
        assert len(kpis) >= 6

        back_to_studio = await page.query_selector(".admin-back-btn")
        await back_to_studio.click()
        await page.wait_for_selector(".studio-card", timeout=5000)
        print("  [PASS] Switched from Admin Dashboard back to Studio Workspace.")

        admin_tag = await page.inner_text(".user-greeting .role-tag")
        print(f"  [PASS] Studio header confirms role tag: '{admin_tag}'")
        assert admin_tag == "ADMIN"

        studio_admin_btn = await page.query_selector(".btn-admin-nav")
        await studio_admin_btn.click()
        await page.wait_for_selector(".admin-container", timeout=5000)
        print("  [PASS] Re-entered Admin Dashboard via header button.")

        admin_logout_btn = await page.wait_for_selector(".btn-danger-outline", timeout=5000)
        await admin_logout_btn.click()
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("  [PASS] Admin logged out successfully, gated back to Login.")

        if console_errors:
            print(f"\n[WARNING] Captured {len(console_errors)} console errors: {console_errors}")
        else:
            print("\n  [PASS] 0 browser console errors captured!")

        await browser.close()
        print("\n==================================================")
        print("ALL 8 E2E STARTUP & ROUTE PROTECTION TESTS PASSED!")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())


