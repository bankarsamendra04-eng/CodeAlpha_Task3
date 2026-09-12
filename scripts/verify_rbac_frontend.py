import asyncio
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"

async def run_frontend_rbac_tests():
    print("==================================================")
    print("E2E FRONTEND STRICT RBAC & ROUTE PROTECTION TESTS")
    print("==================================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # SCENARIO 1: Unauthenticated -> Admin dashboard = DENY
        print("\n[SCENARIO 1] Unauthenticated visitor trying to view Admin dashboard...")
        await page.goto(FRONTEND_URL)
        # Verify unauthenticated visitor gets gated at login
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        has_admin = await page.query_selector(".admin-container")
        assert has_admin is None, "Unauthenticated visitor must NOT see Admin dashboard!"
        print("  [PASS] Unauthenticated visitor gated at login; Admin dashboard access DENIED.")

        # SCENARIO 2: USER -> User dashboard = ALLOW
        print("\n[SCENARIO 2] USER -> User dashboard (Studio Workspace) = ALLOW...")
        inputs = await page.query_selector_all(".auth-input")
        await inputs[0].fill("user")
        await inputs[1].fill("UserPass123!")
        await page.click("button[type='submit']")
        await page.wait_for_selector(".studio-card", timeout=8000)
        print("  [PASS] Standard USER successfully loaded User Studio dashboard.")

        # SCENARIO 3: USER -> Admin dashboard = DENY
        print("\n[SCENARIO 3] USER attempting to access Admin dashboard...")
        # Check that Admin navigation button is NOT in DOM
        admin_btn = await page.query_selector(".btn-admin-nav")
        assert admin_btn is None, "USER must not see Admin navigation button!"

        # Attempt privilege escalation via localStorage tampering:
        print("  Testing client tampering (setting role to ADMIN in localStorage)...")
        await page.evaluate("""() => {
            const user = JSON.parse(localStorage.getItem('aimusic_user') || '{}');
            user.role = 'ADMIN';
            localStorage.setItem('aimusic_user', JSON.stringify(user));
        }""")
        await page.reload()
        # Session verification effect on mount calls GET /api/auth/me which returns authentic role=USER
        await page.wait_for_selector(".studio-card", timeout=8000)
        tampered_user_greeting = await page.inner_text(".user-greeting")
        assert "ADMIN" not in tampered_user_greeting
        print("  [PASS] Client role tampering overridden by trusted backend /api/auth/me.")
        admin_btn_after = await page.query_selector(".btn-admin-nav")
        assert admin_btn_after is None
        print("  [PASS] USER access to Admin dashboard strictly DENIED.")

        # SCENARIO 4: ADMIN -> Admin dashboard = ALLOW
        print("\n[SCENARIO 4] ADMIN -> Admin dashboard = ALLOW...")
        # Logout user
        logout_btn = await page.query_selector("button:text('Logout')")
        await logout_btn.click()
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)

        # Login as Admin
        admin_inputs = await page.query_selector_all(".auth-input")
        await admin_inputs[0].fill("samendra_bankar")
        await admin_inputs[1].fill("Samm@2004")
        await page.click("button[type='submit']")

        # Verify landing on Admin dashboard
        await page.wait_for_selector(".admin-container", timeout=8000)
        print("  [PASS] ADMIN successfully entered Admin dashboard.")
        admin_title = await page.inner_text(".admin-title")
        assert "Admin Dashboard" in admin_title
        print("  [PASS] Admin dashboard telemetry rendered for ADMIN.")

        await browser.close()
        print("\n==================================================")
        print("ALL FRONTEND RBAC SCENARIOS VERIFIED SUCCESSFULLY!")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_frontend_rbac_tests())
