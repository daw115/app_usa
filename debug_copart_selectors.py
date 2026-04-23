import asyncio
from playwright.async_api import async_playwright
from backend.services.scrapers.base import storage_state_path

async def find_selectors():
    state_file = storage_state_path("copart")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()

        await page.goto("https://www.copart.com/lotSearchResults/?query=BMW%20X5", timeout=30000)
        await page.wait_for_timeout(8000)

        # Sprawdź różne możliwe selektory
        selectors = [
            ("div[data-uname='lotsearchLotimage']", "Lot image containers"),
            ("a[href*='/lot/']", "Lot links"),
            (".lot-details", "Lot details"),
            ("[data-lot-id]", "Elements with lot ID"),
            ("div.lot-row", "Lot rows"),
            ("table tbody tr", "Table rows"),
        ]

        print("\n=== Szukam elementów aukcji ===")
        for selector, desc in selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    print(f"✓ {desc} ({selector}): {count} znaleziono")
                    if count > 0 and count < 20:
                        first = page.locator(selector).first
                        html = await first.inner_html()
                        print(f"  Przykład HTML: {html[:200]}...")
            except Exception as e:
                print(f"✗ {desc}: błąd - {e}")

        await page.screenshot(path="/tmp/copart_page.png")
        print(f"\nScreenshot zapisany: /tmp/copart_page.png")

        await browser.close()

asyncio.run(find_selectors())
