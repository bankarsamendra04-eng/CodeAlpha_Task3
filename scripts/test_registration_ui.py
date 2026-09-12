import asyncio
import time
from playwright.async_api import async_playwright

FRONTEND_URL = "http://localhost:5173"

async def run_ui_registration_tests():
    print("==================================================")
    print("PLAYWRIGHT REGISTRATION UI VERIFICATION TESTS")
    print("==================================================")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Visit application (gated at standalone login screen)
        await page.goto(FRONTEND_URL)
        await page.wait_for_selector(".auth-card-standalone", timeout=5000)
        print("[1] Reached gatekeeper.")

        # 2. Click Create Account tab
        await page.click("button.auth-card-tab:text('Create Account')")
        await page.wait_for_timeout(300)

        # 3. Verify Account Role dropdown and Admin Verification code are NOT present
        role_select = await page.query_selector("select.auth-input")
        assert role_select is None, "Role selection dropdown must NOT exist in public registration!"
        admin_code = await page.query_selector("input[placeholder*='Admin Secret']")
        assert admin_code is None, "Admin secret input must NOT exist in public registration!"
        print("  [PASS] Public registration form has NO role dropdown and NO admin code input.")

        # 4. Verify fields present: Name/Username, Email, Password, Confirm Password
        labels = await page.eval_on_selector_all(".auth-form .form-label", "els => els.map(e => e.innerText.trim())")
        print(f"  Form fields present: {labels}")
        assert any("Full Name" in l or "Username" in l for l in labels)
        assert any("Email" in l for l in labels)
        assert any("Confirm Password" in l for l in labels)
        print("  [PASS] Required fields (Name, Email, Password, Confirm Password) present.")

        # 5. Test Password Mismatch Validation
        print("\n[2] Testing Password Mismatch error handling...")
        inputs = await page.query_selector_all(".auth-input")
        await inputs[0].fill("Test Artist")
        await inputs[1].fill("testartist@studio.ai")
        await inputs[2].fill("Password123!")
        await inputs[3].fill("DifferentPass123!")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".auth-error", timeout=3000)
        err_text = await page.inner_text(".auth-error")
        print(f"  [PASS] Mismatch error: '{err_text}'")
        assert "Passwords do not match" in err_text
        assert "[object Object]" not in err_text

        # 6. Test Invalid Email Validation
        print("\n[3] Testing Invalid Email error handling...")
        await inputs[1].fill("invalid-email-format")
        await inputs[3].fill("Password123!")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".auth-error", timeout=3000)
        err_email = await page.inner_text(".auth-error")
        print(f"  [PASS] Email error: '{err_email}'")
        assert "valid email" in err_email.lower()
        assert "[object Object]" not in err_email

        # 7. Test Short Password Validation
        print("\n[4] Testing Short Password error handling...")
        await inputs[1].fill("valid@studio.ai")
        await inputs[2].fill("123")
        await inputs[3].fill("123")
        await page.click("button[type='submit']")

        await page.wait_for_selector(".auth-error", timeout=3000)
        err_pw = await page.inner_text(".auth-error")
        print(f"  [PASS] Short password error: '{err_pw}'")
        assert "at least 6 characters" in err_pw
        assert "[object Object]" not in err_pw

        # 8. Test Successful Public Registration
        print("\n[5] Testing Successful Registration...")
        ts = int(time.time())
        new_username = f"artist_{ts}"
        await inputs[0].fill(new_username)
        await inputs[1].fill(f"artist_{ts}@studio.ai")
        await inputs[2].fill("ValidSecretHarmony#2026")
        await inputs[3].fill("ValidSecretHarmony#2026")
        await page.click("button[type='submit']")

        # Enters Studio Workspace
        await page.wait_for_selector(".studio-card", timeout=8000)
        print(f"  [PASS] Successfully registered and landed directly in Studio Workspace!")

        # Verify assigned role is normal USER (no ADMIN privileges)
        greeting = await page.inner_text(".user-greeting")
        print(f"  User profile widget: '{greeting.strip()}'")
        assert new_username in greeting
        assert "ADMIN" not in greeting
        admin_btn = await page.query_selector(".btn-admin-nav")
        assert admin_btn is None, "New registered user must NOT have admin navigation!"
        print("  [PASS] Automatically assigned USER role with no ADMIN access.")

        await browser.close()
        print("\n==================================================")
        print("ALL REGISTRATION UI TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_ui_registration_tests())
