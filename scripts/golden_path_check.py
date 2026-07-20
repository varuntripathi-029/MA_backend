"""One-off visual golden-path check of the frontend against a live backend.
Not part of the pytest suite (needs a running dev server + real network) —
run manually: python scripts/golden_path_check.py
"""

import asyncio
import sys

from playwright.async_api import async_playwright

SCRATCH = "C:/Users/Asus/AppData/Local/Temp/claude/D--proj-pm-MX-rating/1f78af79-6473-4dfa-990a-3fb848937277/scratchpad"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", lambda msg: print("[console]", msg.type, msg.text))
        page.on("pageerror", lambda exc: print("[pageerror]", exc))
        page.on("requestfailed", lambda req: print("[requestfailed]", req.url, req.failure))

        await page.goto("http://localhost:3000", wait_until="networkidle")
        await page.screenshot(path=f"{SCRATCH}/gp_01_landing.png")
        print("landing page loaded, title:", await page.title())

        await page.fill('input[placeholder="example.com"]', "https://stripe.com")
        await page.click('button:has-text("Scan site")')
        try:
            await page.wait_for_url("**/report/*", timeout=15000)
            print("navigated to:", page.url)
        except Exception as e:
            print("nav wait failed:", e, "current url:", page.url)
            await page.screenshot(path=f"{SCRATCH}/gp_01b_after_click.png")
            body_text = await page.inner_text("body")
            print("body text snippet:", body_text[:500])

        await page.wait_for_timeout(1200)
        await page.screenshot(path=f"{SCRATCH}/gp_02_polling.png")
        print("polling state screenshot taken")

        try:
            await page.wait_for_selector("text=AI-agent readiness score for", timeout=90000)
        except Exception as e:
            await page.screenshot(path=f"{SCRATCH}/gp_02b_timeout.png")
            print("TIMEOUT waiting for report:", e)
            await browser.close()
            return

        await page.wait_for_timeout(1500)
        await page.screenshot(path=f"{SCRATCH}/gp_03_report.png", full_page=True)
        print("report rendered, screenshot taken")

        # expand a finding card
        finding_button = page.locator("text=All findings").locator("..").locator("button").first
        await page.locator("text=All findings").scroll_into_view_if_needed()
        first_finding = page.locator("h2:has-text('All findings') ~ div button").first
        await first_finding.click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=f"{SCRATCH}/gp_04_finding_expanded.png", full_page=True)
        print("finding expanded, screenshot taken")

        # hover state on nav link
        await page.hover("text=Methodology")
        await page.wait_for_timeout(300)
        await page.screenshot(path=f"{SCRATCH}/gp_05_nav_hover.png")
        print("nav hover screenshot taken")

        # methodology page
        await page.click("text=Methodology")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(800)
        await page.screenshot(path=f"{SCRATCH}/gp_06_methodology.png", full_page=True)
        print("methodology page screenshot taken")

        # history page
        await page.click("text=History")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(800)
        await page.screenshot(path=f"{SCRATCH}/gp_07_history.png", full_page=True)
        print("history page screenshot taken")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
