"""Debug script to test Copart photo scraping on live site"""
import asyncio
from playwright.async_api import async_playwright

async def test_copart_photos():
    # Test URL - 2013 BMW X5
    test_url = "https://www.copart.com/lot/99885295"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print(f"Loading: {test_url}")
            await page.goto(test_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)

            # Strategy 1: Gallery images
            print("\n=== Strategy 1: Gallery images ===")
            gallery_imgs = await page.query_selector_all("img[src*='cs.copart.com'], img[data-src*='cs.copart.com']")
            print(f"Found {len(gallery_imgs)} gallery images")

            photos = []
            for i, img in enumerate(gallery_imgs[:10]):
                src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
                if src and "cs.copart.com" in src:
                    full_src = src.replace("_thb.jpg", "_ful.jpg").replace("_hrs.jpg", "_ful.jpg")
                    print(f"  {i+1}. {full_src}")
                    if "lpp" in full_src:
                        photos.append(full_src)

            # Strategy 2: Regex in page content
            print("\n=== Strategy 2: Regex in HTML ===")
            content = await page.content()
            import re
            urls = re.findall(r'https://cs\.copart\.com/[^"\'>\s]+_ful\.jpg', content)
            print(f"Found {len(urls)} URLs via regex")
            for i, url in enumerate(urls[:10]):
                print(f"  {i+1}. {url}")
                if url not in photos:
                    photos.append(url)

            # Strategy 3: Check for image viewer/carousel
            print("\n=== Strategy 3: Image viewer elements ===")
            selectors = [
                ".image-gallery img",
                "[data-testid='image-gallery'] img",
                ".carousel img",
                ".lot-image img",
                "[class*='image'] img[src*='copart']",
            ]
            for sel in selectors:
                imgs = await page.query_selector_all(sel)
                if imgs:
                    print(f"  Selector '{sel}': {len(imgs)} images")
                    for img in imgs[:3]:
                        src = await img.get_attribute("src") or ""
                        if src:
                            print(f"    - {src[:100]}")

            print(f"\n=== TOTAL UNIQUE PHOTOS: {len(photos)} ===")

            # Keep browser open for manual inspection
            print("\nBrowser will stay open for 60s for manual inspection...")
            await page.wait_for_timeout(60000)

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_copart_photos())
