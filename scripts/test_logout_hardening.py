import asyncio
import time
import requests
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://127.0.0.1:8000"

async def test_logout_and_session_hardening():
    print("==================================================")
    print("LOGOUT & SESSION HARDENING VERIFICATION")
    print("==================================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # -------------------------------------------------------------
        # TEST 1: Login -> protected page -> logout -> refresh -> Login
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing: Login -> protected page -> logout -> refresh -> Login...")
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)

        # Login
        inputs = await page.query_selector_all(".auth-input")
        await inputs[0].fill("user")
        await inputs[1].fill("UserPass123!")
        await page.click("button[type='submit']")

        # Enters protected page
        await page.wait_for_selector(".studio-card", timeout=8000)
        print("  [PASS] Successfully logged in to protected Studio page.")

        # Capture token from localStorage before logout
        active_token = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        assert active_token is not None, "Token must be present while logged in!"

        # Click Logout
        logout_btn = await page.query_selector("button:text('Logout')")
        await logout_btn.click()
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("  [PASS] Logout immediately returned to Login screen.")

        # Verify frontend storage is wiped
        token_after_logout = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        user_after_logout = await page.evaluate("() => localStorage.getItem('aimusic_user')")
        assert token_after_logout is None, "Token must be completely purged from localStorage!"
        assert user_after_logout is None, "User profile must be completely purged from localStorage!"
        print("  [PASS] localStorage cleared: no sensitive tokens or user data remain.")

        # Refresh after logout
        await page.reload()
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        has_studio = await page.query_selector(".studio-card")
        assert has_studio is None, "Protected studio page must NOT be visible after refresh!"
        print("  [PASS] Refresh after logout continues to show Login gate strictly.")

        # -------------------------------------------------------------
        # TEST 2: Protected pages no longer accessible
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing: Direct navigation without session cannot access dashboard...")
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        has_studio_direct = await page.query_selector(".studio-card")
        assert has_studio_direct is None, "Protected studio state must not be visible without session!"
        print("  [PASS] Protected pages remain completely inaccessible.")

        # -------------------------------------------------------------
        # TEST 3: Login -> logout -> call protected API -> DENY
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing: Login -> logout -> call protected API -> DENY...")
        # Verify that calls without a token (or with cleared token) are rejected
        res_no_token = requests.get(f"{BACKEND_URL}/api/subscription/me")
        print(f"  GET /api/subscription/me without token -> Status: {res_no_token.status_code}")
        assert res_no_token.status_code == 401, f"Expected 401, got {res_no_token.status_code}"

        res_admin_no_token = requests.get(f"{BACKEND_URL}/api/admin/dashboard")
        print(f"  GET /api/admin/dashboard without token -> Status: {res_admin_no_token.status_code}")
        assert res_admin_no_token.status_code == 401, f"Expected 401, got {res_admin_no_token.status_code}"
        print("  [PASS] Protected API requests without active token strictly denied with HTTP 401.")

        # -------------------------------------------------------------
        # TEST 4: Expired / Invalid token automatic redirection to Login
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing: Expired / invalid authentication auto-redirects to Login...")
        # Inject an expired / invalid JWT token into localStorage
        await page.evaluate("""() => {
            localStorage.setItem('aimusic_token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NSIsImV4cCI6MTYwMDAwMDAwMH0.signature');
            localStorage.setItem('aimusic_user', JSON.stringify({username: 'ghost', role: 'USER'}));
        }""")
        await page.reload()
        # The verifySession hook queries /api/auth/me which returns 401, triggering immediate logout and gatekeeper
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        purged_token = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        assert purged_token is None, "Expired token must be wiped from localStorage!"
        print("  [PASS] Expired authentication automatically intercepted, wiped, and redirected to Login.")

        await browser.close()
        print("\n==================================================")
        print("ALL LOGOUT & SESSION HARDENING TESTS PASSED!")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_logout_and_session_hardening())
