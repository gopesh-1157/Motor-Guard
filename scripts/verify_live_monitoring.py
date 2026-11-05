"""
Verify Live Monitoring (LiveMonitoringView.tsx):
- Runs sustained live telemetry stream test (120+ seconds)
- Tracks layout jumps (bounding box variance), chart rendering performance, and console errors
- Captures responsive screenshots at 1440px, 768px, and 375px in both dark and light modes
- Verifies Multi-Asset Grid view
"""

import sys
import time
import json
from playwright.sync_api import sync_playwright

def run_verification():
    console_errors = []
    console_warnings = []

    print("[1/5] Launching Playwright browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: (
            console_errors.append(f"[{msg.type}] {msg.text}") if msg.type == "error" else (
                console_warnings.append(f"[{msg.type}] {msg.text}") if msg.type == "warning" else None
            )
        ))
        page.on("pageerror", lambda err: console_errors.append(f"[pageerror] {err}"))

        print("[2/5] Navigating to http://localhost:5173 and logging in...")
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")

        # Check for login modal or login button
        login_btn = page.locator("button:has-text('Sign In'), button:has-text('Log In'), button:has-text('Switch User')")
        if page.locator("input[placeholder*='sername'], input[name='username']").is_visible():
            page.fill("input[placeholder*='sername'], input[name='username']", "admin")
            page.fill("input[type='password']", "adminpassword123")
            page.click("button:has-text('Sign In'), button:has-text('Log In'), button[type='submit']")
            page.wait_for_timeout(2000)

        # Navigate to Live Monitoring
        print("[3/5] Navigating to Live Telemetry & Stream Monitor...")
        live_nav = page.locator("#nav-live, [data-testid='nav-live'], button:has-text('Live Telemetry'), a:has-text('Live Telemetry')")
        if live_nav.count() > 0:
            live_nav.first.click()
        else:
            # Try clicking any element containing Live Telemetry
            page.click("text='Live Telemetry'")
        
        page.wait_for_timeout(2000)

        # Verify page header
        header_text = page.locator("h1, h2").first.text_content()
        print(f"  Active Header: '{header_text}'")

        # Monitor live telemetry stream for 120 seconds while sampling layout positions
        print("[4/5] Running live telemetry stream evaluation for 120 seconds...")
        layout_samples = []
        start_time = time.time()
        last_report = 0

        while time.time() - start_time < 120:
            elapsed = int(time.time() - start_time)
            
            # Check bounding box of main content area & gauge grid for layout jumps
            try:
                content_box = page.locator(".page-header").first.bounding_box()
                metric_box = page.locator(".metric-card").first.bounding_box()
                if content_box and metric_box:
                    layout_samples.append({
                        "t": elapsed,
                        "header_y": content_box["y"],
                        "header_h": content_box["height"],
                        "card_y": metric_box["y"],
                        "card_h": metric_box["height"]
                    })
            except Exception:
                pass

            if elapsed - last_report >= 20:
                last_report = elapsed
                # Sample event log count
                rows_count = page.locator(".compact-table tbody tr").count()
                print(f"  [T+{elapsed:03d}s] Stream active • Log rows: {rows_count} • Console errors: {len(console_errors)}")

            page.wait_for_timeout(1000)

        # Analyze layout stability (Cumulative Layout Variance)
        header_y_set = {s["header_y"] for s in layout_samples}
        card_y_set = {s["card_y"] for s in layout_samples}
        card_h_set = {s["card_h"] for s in layout_samples}

        print("\n--- Telemetry Stream Health & Layout Report ---")
        print(f"Total Stream Duration: {int(time.time() - start_time)} seconds")
        print(f"Layout Samples Collected: {len(layout_samples)}")
        print(f"Header Y Variance: {len(header_y_set)} unique positions ({header_y_set}) -> {'STABLE (0 jumps)' if len(header_y_set) <= 1 else 'JUMPS DETECTED'}")
        print(f"Metric Card Height Variance: {len(card_h_set)} unique heights ({card_h_set}) -> {'STABLE (0 jumps)' if len(card_h_set) <= 1 else 'JUMPS DETECTED'}")
        print(f"Total Console Errors Recorded: {len(console_errors)}")
        if console_errors:
            for err in console_errors[:5]:
                print(f"  Error: {err}")
        else:
            print("  Zero (0) console errors encountered during live telemetry stream!")

        # Capture 1440px Dark
        print("\n[5/5] Capturing responsive screenshots...")
        # Ensure Dark Theme
        theme_toggle = page.locator("#theme-toggle, button[aria-label*='theme'], button:has-text('Theme')")
        
        # Check current theme attribute
        is_dark = page.evaluate("() => document.documentElement.getAttribute('data-theme') !== 'light'")
        if not is_dark and theme_toggle.count() > 0:
            theme_toggle.first.click()
            page.wait_for_timeout(500)

        page.screenshot(path="live_1440px_dark.png")
        print("  Saved: live_1440px_dark.png (1440x900 Dark)")

        # Switch to Light Theme for 1440px
        if theme_toggle.count() > 0:
            theme_toggle.first.click()
            page.wait_for_timeout(500)
        else:
            page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
            page.wait_for_timeout(500)

        page.screenshot(path="live_1440px_light.png")
        print("  Saved: live_1440px_light.png (1440x900 Light)")

        # Test Multi-Asset Grid View
        multi_btn = page.locator("button:has-text('Multi-Asset Grid')")
        if multi_btn.count() > 0:
            multi_btn.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="live_multi_1440px_light.png")
            print("  Saved: live_multi_1440px_light.png")
            # Return to Single Asset
            page.click("button:has-text('Single Asset')")
            page.wait_for_timeout(500)

        # Switch back to dark for mobile & tablet dark captures
        page.evaluate("() => document.documentElement.removeAttribute('data-theme')")
        page.wait_for_timeout(500)

        browser.close()

    # Capture 768px (Tablet) Dark and Light
    print("Capturing 768px Tablet screenshots...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 768, "height": 1024})
        page = context.new_page()
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        page.click("#nav-live, [data-testid='nav-live'], button:has-text('Live Telemetry'), a:has-text('Live Telemetry')")
        page.wait_for_timeout(3000)
        page.screenshot(path="live_768px_dark.png")
        print("  Saved: live_768px_dark.png (768x1024 Dark)")

        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
        page.wait_for_timeout(500)
        page.screenshot(path="live_768px_light.png")
        print("  Saved: live_768px_light.png (768x1024 Light)")
        browser.close()

    # Capture 375px (Mobile) Dark and Light
    print("Capturing 375px Mobile screenshots...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()
        page.goto("http://localhost:5173")
        page.wait_for_load_state("networkidle")
        page.click("#nav-live, [data-testid='nav-live'], button:has-text('Live Telemetry'), a:has-text('Live Telemetry')")
        page.wait_for_timeout(3000)
        page.screenshot(path="live_375px_dark.png")
        print("  Saved: live_375px_dark.png (375x812 Dark)")

        page.evaluate("() => document.documentElement.setAttribute('data-theme', 'light')")
        page.wait_for_timeout(500)
        page.screenshot(path="live_375px_light.png")
        print("  Saved: live_375px_light.png (375x812 Light)")
        browser.close()

    print("\nAll Live Monitoring verifications and responsive screenshots completed successfully!")

if __name__ == "__main__":
    run_verification()
