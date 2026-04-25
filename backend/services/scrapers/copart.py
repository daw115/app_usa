from __future__ import annotations

import logging
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.config import config
from backend.services.scrapers.base import (
    ScrapedListing,
    SearchCriteria,
    jitter,
    storage_state_path,
)

log = logging.getLogger(__name__)

COPART_SEARCH_TPL = "https://www.copart.com/lotSearchResults/?query={query}"


def _build_query(c: SearchCriteria) -> str:
    parts = [p for p in (c.make, c.model) if p]
    return quote(" ".join(parts) or "cars")


async def search(criteria: SearchCriteria) -> list[ScrapedListing]:
    """Scrape Copart search results. Requires a logged-in storage state file
    (playwright_profiles/copart.json). Create it with:
        python -m backend.services.scrapers.login_helper copart
    """
    state_file = storage_state_path("copart")
    if not state_file.exists():
        log.warning("Copart storage_state missing at %s — skipping.", state_file)
        return []

    results: list[ScrapedListing] = []
    browser = None
    context = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=str(state_file))
            page = await context.new_page()

            try:
                url = COPART_SEARCH_TPL.format(query=_build_query(criteria))
                log.info(f"Copart: Loading search page {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await jitter()
                await page.wait_for_timeout(3000)

                lot_links = await page.query_selector_all("a[href*='/lot/']")
                seen_urls = set()
                log.info(f"Copart: Found {len(lot_links)} lot links")

                for link in lot_links:
                    if len(results) >= criteria.max_results:
                        break
                    try:
                        href = await link.get_attribute("href") or ""
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)

                        if href.startswith("/"):
                            href = "https://www.copart.com" + href

                        parts = href.split("/")
                        if len(parts) >= 6:
                            title = parts[5].replace("-", " ").title()
                        else:
                            title = f"Copart Lot {parts[4] if len(parts) > 4 else ''}"

                        results.append(ScrapedListing(
                            source="copart",
                            source_url=href,
                            title=title,
                        ))
                    except Exception as e:
                        log.warning(f"Copart: Failed to parse link: {e}")
                        continue

                for listing in results:
                    try:
                        log.debug(f"Copart: Fetching details for {listing.source_url}")
                        await page.goto(listing.source_url, wait_until="domcontentloaded", timeout=30000)
                        await jitter()
                        await _enrich_detail(page, listing)
                    except Exception as e:
                        log.error(f"Copart: Failed to fetch details for {listing.source_url}: {e}")
                        continue

            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()

    except Exception as e:
        log.error(f"Copart search failed: {e}", exc_info=True)
        if browser:
            try:
                await browser.close()
            except:
                pass

    log.info(f"Copart: Returning {len(results)} listings")
    return results


def _parse_usd(s: str) -> float | None:
    if not s:
        return None
    t = s.replace("$", "").replace(",", "").replace("USD", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


async def _enrich_detail(page, listing: ScrapedListing) -> None:
    # VIN
    for sel in ["[data-uname='lotdetailVinvalue']", "span:has-text('VIN')", ".vin-number", "[data-testid='vin']"]:
        vin_el = await page.query_selector(sel)
        if vin_el:
            listing.vin = (await vin_el.inner_text()).strip()[:17]
            break

    # Photos - wait for images to load
    await page.wait_for_timeout(3000)

    # Strategy 1: Gallery images with cs.copart.com
    gallery_imgs = await page.query_selector_all("img[src*='cs.copart.com'], img[data-src*='cs.copart.com']")
    for img in gallery_imgs[:20]:
        src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
        if src and "cs.copart.com" in src and "lpp" in src:
            # Convert thumbnails to full-size
            full_src = src.replace("_thb.jpg", "_ful.jpg").replace("_hrs.jpg", "_ful.jpg").replace("_thn.jpg", "_ful.jpg")
            if full_src not in listing.photos:
                listing.photos.append(full_src)

    # Strategy 2: Regex in HTML (fallback if Strategy 1 found <3 photos)
    if len(listing.photos) < 3:
        content = await page.content()
        import re
        urls = re.findall(r'https://cs\.copart\.com/[^"\'>\s]+lpp[^"\'>\s]+_ful\.jpg', content)
        for url in urls[:15]:
            if url not in listing.photos:
                listing.photos.append(url)

    log.info(f"Found {len(listing.photos)} photos for {listing.source_url}")


def is_configured() -> bool:
    return storage_state_path("copart").exists() or bool(config.copart_username and config.copart_password)
