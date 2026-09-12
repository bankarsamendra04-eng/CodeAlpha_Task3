import asyncio
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"

async def test_login_behavior():
    print("==================================================")
    print("RUNNING LOGIN PAGE BEHAVIOR VERIFICATION")
    print("==================================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Visit Login Page
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("[1] Reached standalone login page.")

        # Check UI components
        label = await page.inner_text(".auth-form .form-label")
        print(f"  Field label: '{label}'")
        assert "Email or Username" in label

        password_input = await page.query_selector("input[type='password']")
        assert password_input is not None, "Password input must have type='password' (masked)!"
        print("  [PASS] Password field is strictly masked (type='password').")

        submit_btn = await page.query_selector("button[type='submit']")
        submit_text = await submit_btn.inner_text()
        print(f"  Sign In Button: '{submit_text.encode('ascii', 'ignore').decode()}'")
        assert "Sign In" in submit_text

        # Create Account option exists
        register_tab = await page.query_selector("button.auth-card-tab:text('Create Account')")
        assert register_tab is not None
        print("  [PASS] 'Create Account' option is readily accessible.")

        # 2. Test Empty Username
        print("\n[2] Testing Empty Username Validation...")
        await page.click("button[type='submit']")
        await page.wait_for_selector(".auth-error", timeout=3000)
        err_user = await page.inner_text(".auth-error")
        print(f"  [PASS] Error on empty username: '{err_user}'")
        assert "Please enter your email address or username" in err_user
        assert "[object Object]" not in err_user

        # 3. Test Empty Password
        print("\n[3] Testing Empty Password Validation...")
        username_input = await page.query_selector(".auth-input")
        await username_input.fill("user")
        await page.click("button[type='submit']")
        await page.wait_for_selector(".auth-error", timeout=3000)
        err_pw = await page.inner_text(".auth-error")
        print(f"  [PASS] Error on empty password: '{err_pw}'")
        assert "Please enter your password" in err_pw
        assert "[object Object]" not in err_pw

        # 4. Test Wrong Credentials
        print("\n[4] Testing Wrong Credentials...")
        await password_input.fill("IncorrectPassword#999")
        await page.click("button[type='submit']")
        await page.wait_for_selector(".auth-error", timeout=5000)
        err_wrong = await page.inner_text(".auth-error")
        print(f"  [PASS] Error on wrong credentials: '{err_wrong}'")
        assert "Invalid username or password" in err_wrong
        assert "[object Object]" not in err_wrong

        # 5. Test Normal USER Login
        print("\n[5] Testing Standard USER Login ('user' / 'UserPass123!')...")
        await username_input.fill("user")
        await password_input.fill("UserPass123!")
        await page.click("button[type='submit']")

        # Redirects to User Studio Dashboard
        await page.wait_for_selector(".studio-card", timeout=8000)
        print("  [PASS] USER successfully logged in and redirected to User Studio Dashboard.")

        # Check persistence
        saved_token = await page.evaluate("() => localStorage.getItem('aimusic_token')")
        saved_user = await page.evaluate("() => JSON.parse(localStorage.getItem('aimusic_user'))")
        assert saved_token is not None
        assert saved_user["role"] == "USER"
        print("  [PASS] USER session successfully persisted in localStorage.")

        # Logout USER
        logout_btn = await page.query_selector("button:text('Logout')")
        await logout_btn.click()
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("  [PASS] Logged out back to Login page.")

        # 6. Test ADMIN Login by Email
        print("\n[6] Testing ADMIN Login by Email ('bankarsamendra04@gmail.com' / 'Samm@2004')...")
        admin_user_input = await page.query_selector(".auth-input")
        admin_pw_input = await page.query_selector("input[type='password']")
        await admin_user_input.fill("bankarsamendra04@gmail.com")
        await admin_pw_input.fill("Samm@2004")
        await page.click("button[type='submit']")

        # Redirects to Admin Dashboard
        await page.wait_for_selector(".admin-container", timeout=8000)
        admin_heading = await page.inner_text(".admin-title")
        print(f"  [PASS] ADMIN successfully logged in and redirected to: '{admin_heading.encode('ascii', 'ignore').decode()}'")
        assert "Admin Dashboard" in admin_heading

        # Check admin session persistence
        admin_saved_user = await page.evaluate("() => JSON.parse(localStorage.getItem('aimusic_user'))")
        assert admin_saved_user["role"] == "ADMIN"
        print("  [PASS] ADMIN session successfully persisted with role 'ADMIN'.")

        await browser.close()
        print("\n==================================================")
        print("ALL LOGIN PAGE BEHAVIOR TESTS PASSED!")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(test_login_behavior())

