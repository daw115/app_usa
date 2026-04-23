import asyncio
from playwright.async_api import async_playwright
from backend.services.scrapers.base import storage_state_path

async def auto_login():
    out = storage_state_path("copart")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.copart.com/login/")
        await page.wait_for_load_state("networkidle")

        # Wait and find login fields
        await page.wait_for_timeout(3000)

        # Try multiple selectors
        try:
            await page.fill('#username', 'usacarsbitches@proton.me')
            await page.fill('#password', 'vankif-2sujno-cudtEk')
        except:
            await page.fill('input[type="email"]', 'usacarsbitches@proton.me')
            await page.fill('input[type="password"]', 'vankif-2sujno-cudtEk')

        await page.click('button[type="submit"], input[type="submit"]')

        # Wait longer for login
        await page.wait_for_timeout(10000)

        # Save session
        await context.storage_state(path=str(out))
        print(f"✓ Sesja zapisana: {out}")
        await browser.close()

asyncio.run(auto_login())
