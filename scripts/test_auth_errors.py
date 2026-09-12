"""
Automated Browser Verification for Authentication Error-Display System.
Tests:
1. Wrong email / unregistered user login
2. Wrong password login
3. Invalid registration format (short password, bad username, malformed email)
4. Duplicate email / username registration
5. Backend unavailable error handling
6. Successful login (Admin & User)
"""

import sys
import time
import subprocess
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_auth_error_verification():
    print("=" * 60)
    print("AUTHENTICATION ERROR HANDLING SYSTEM VERIFICATION")
    print("=" * 60)

    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=True,
            args=["--autoplay-policy=no-user-gesture-required"]
        )
        context = browser.new_context()
        page = context.new_page()

        # Navigate to frontend
        print("\n[Step 1] Loading application at http://localhost:5173...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        time.sleep(1)

        # Open Auth Modal
        sign_in_btn = page.locator("button:has-text('Admin / Sign In')")
        sign_in_btn.click()
        page.wait_for_selector(".auth-modal", state="visible")
        print("  Auth modal opened successfully.")

        # -------------------------------------------------------------
        # Test 1: Wrong Email / Unregistered User
        # -------------------------------------------------------------
        print("\n[Test 1] Testing wrong email / unregistered user login...")
        username_input = page.locator(".auth-input[type='text']")
        password_input = page.locator(".auth-input[type='password']")
        submit_btn = page.locator(".auth-modal button[type='submit']")

        username_input.fill("nonexistent_user_999@test.com")
        password_input.fill("AnyPassword123!")
        submit_btn.click()

        page.wait_for_selector(".auth-error", state="visible", timeout=5000)
        err_text_1 = page.locator(".auth-error").inner_text()
        print(f"  Observed error message: '{err_text_1}'")
        assert "[object Object]" not in err_text_1, "Error contains [object Object]!"
        assert "Invalid username or password" in err_text_1, f"Unexpected error: {err_text_1}"
        results["Wrong Email / Account"] = f"PASS ({err_text_1})"

        # -------------------------------------------------------------
        # Test 2: Wrong Password
        # -------------------------------------------------------------
        print("\n[Test 2] Testing wrong password login on existing account...")
        username_input.fill("admin")
        password_input.fill("WrongSecretPassword999!")
        submit_btn.click()

        page.wait_for_selector(".auth-error", state="visible", timeout=5000)
        err_text_2 = page.locator(".auth-error").inner_text()
        print(f"  Observed error message: '{err_text_2}'")
        assert "[object Object]" not in err_text_2
        assert "Invalid username or password" in err_text_2
        results["Wrong Password"] = f"PASS ({err_text_2})"

        # -------------------------------------------------------------
        # Test 3: Invalid Registration Validation (Pydantic 422 list)
        # -------------------------------------------------------------
        print("\n[Test 3] Testing invalid registration (short password, bad username)...")
        create_tab = page.locator(".auth-tab:has-text('Create Account')")
        create_tab.click()
        time.sleep(0.5)

        username_reg = page.locator(".auth-input[placeholder*='maestro']")
        email_reg = page.locator(".auth-input[type='email']")
        password_reg = page.locator(".auth-input[type='password']")

        # Remove HTML5 required attribute to let Pydantic server-side validation run
        page.evaluate("""() => {
            const form = document.querySelector('.auth-form');
            const inputs = form.querySelectorAll('input');
            inputs.forEach(i => {
                i.removeAttribute('required');
                i.removeAttribute('minlength');
            });
        }""")

        username_reg.fill("a!")  # Invalid format (<3 chars, regex fail)
        email_reg.fill("bad-email")  # Malformed email
        password_reg.fill("123")  # Short password (<6 chars)
        submit_btn.click()

        page.wait_for_selector(".auth-error", state="visible", timeout=5000)
        err_text_3 = page.locator(".auth-error").inner_text()
        print(f"  Observed error message: '{err_text_3}'")
        assert "[object Object]" not in err_text_3, "Error displayed [object Object]!"
        assert len(err_text_3) > 10, "Error message too short!"
        results["Invalid Registration Validation"] = f"PASS ({err_text_3})"

        # -------------------------------------------------------------
        # Test 4: Duplicate Email Registration (HTTP 400)
        # -------------------------------------------------------------
        print("\n[Test 4] Testing duplicate email registration...")
        username_reg.fill(f"newuser_{int(time.time())}")
        email_reg.fill("admin@aimusicstudio.io")  # Existing seeded email
        password_reg.fill("ValidPassword123!")
        submit_btn.click()

        page.wait_for_selector(".auth-error", state="visible", timeout=5000)
        err_text_4 = page.locator(".auth-error").inner_text()
        print(f"  Observed error message: '{err_text_4}'")
        assert "[object Object]" not in err_text_4
        assert "Email address is already registered" in err_text_4 or "registered" in err_text_4
        results["Duplicate Email"] = f"PASS ({err_text_4})"

        # -------------------------------------------------------------
        # Test 5: Backend Unavailable Error Handling
        # -------------------------------------------------------------
        print("\n[Test 5] Testing backend unavailable error handling...")
        # Route abort simulation
        page.route("**/api/auth/*", lambda route: route.abort("failed"))

        sign_in_tab = page.locator(".auth-tab:has-text('Sign In')")
        sign_in_tab.click()
        username_input.fill("admin")
        password_input.fill("AdminPass123!")
        submit_btn.click()

        page.wait_for_selector(".auth-error", state="visible", timeout=5000)
        err_text_5 = page.locator(".auth-error").inner_text()
        print(f"  Observed error message: '{err_text_5}'")
        assert "[object Object]" not in err_text_5
        assert "unavailable" in err_text_5.lower() or "server" in err_text_5.lower()
        results["Backend Unavailable"] = f"PASS ({err_text_5})"

        # Unroute abort
        page.unroute("**/api/auth/*")

        # -------------------------------------------------------------
        # Test 6: Successful Login
        # -------------------------------------------------------------
        print("\n[Test 6] Testing successful login with seeded 'admin' account...")
        username_input.fill("admin")
        password_input.fill("AdminPass123!")
        submit_btn.click()

        # Admin login redirects to Admin Dashboard
        page.wait_for_selector(".admin-container", state="visible", timeout=8000)
        print("  Admin Dashboard loaded successfully!")
        admin_title = page.locator(".admin-title").inner_text()
        print(f"  Dashboard header: '{admin_title}'")
        assert "Admin Dashboard" in admin_title
        results["Successful Login"] = "PASS (Redirected to Admin Dashboard)"

        browser.close()

    print("\n" + "=" * 60)
    print("SUMMARY RESULTS")
    print("=" * 60)
    for test, res in results.items():
        print(f"{test}: {res}")

if __name__ == "__main__":
    run_auth_error_verification()
