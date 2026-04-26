from __future__ import annotations

import logging
from urllib.parse import quote

from playwright.async_api import async_playwright

from backend.services.scrapers.base import (
    ScrapedListing,
    SearchCriteria,
    jitter,
    storage_state_path,
)

log = logging.getLogger(__name__)

AMERPOL_SEARCH_TPL = "https://amerpol.pl/samochody?q={q}"


async def search(criteria: SearchCriteria) -> list[ScrapedListing]:
    """Amerpol scraper — starts with Playwright because selectors vary.
    If the site exposes a JSON XHR we can migrate to httpx later (see TODO in README).
    """
    state_file = storage_state_path("amerpol")
    q = quote(f"{criteria.make} {criteria.model}".strip() or "")
    results: list[ScrapedListing] = []
    browser = None
    context = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            kwargs = {"ignore_https_errors": True}
            if state_file.exists():
                kwargs["storage_state"] = str(state_file)
            context = await browser.new_context(**kwargs)
            page = await context.new_page()

            try:
                log.info(f"Amerpol: Loading search page for '{q}'")
                await page.goto(AMERPOL_SEARCH_TPL.format(q=q), wait_until="domcontentloaded", timeout=30000)
                await jitter()

                cards = await page.query_selector_all("a[href*='/samochod/'], article a[href*='/lot/']")
                log.info(f"Amerpol: Found {len(cards)} result cards")

                seen = set()
                for card in cards[: criteria.max_results * 2]:
                    try:
                        href = await card.get_attribute("href") or ""
                        if not href or href in seen:
                            continue
                        seen.add(href)
                        if href.startswith("/"):
                            href = "https://amerpol.pl" + href
                        title = (await card.inner_text()).strip().split("\n")[0]
                        results.append(ScrapedListing(source="amerpol", source_url=href, title=title))
                        if len(results) >= criteria.max_results:
                            break
                    except Exception as e:
                        log.warning(f"Amerpol: Failed to parse result card: {e}")
                        continue

                for listing in results:
                    try:
                        log.debug(f"Amerpol: Fetching details for {listing.source_url}")
                        await page.goto(listing.source_url, wait_until="domcontentloaded", timeout=30000)
                        await jitter()
                        await _enrich_detail(page, listing)
                    except Exception as e:
                        log.error(f"Amerpol: Failed to fetch details for {listing.source_url}: {e}")
                        continue

            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()

    except Exception as e:
        log.error(f"Amerpol search failed: {e}", exc_info=True)
        if browser:
            try:
                await browser.close()
            except:
                pass

    log.info(f"Amerpol: Returning {len(results)} listings")
    return results


async def _enrich_detail(page, listing: ScrapedListing) -> None:
    for sel in ["[data-vin]", ".vin", "dt:has-text('VIN') + dd"]:
        el = await page.query_selector(sel)
        if el:
            text = (await el.inner_text()).strip()
            if text:
                listing.vin = text[:17]
                break
    imgs = await page.query_selector_all("img")
    for img in imgs[:15]:
        src = await img.get_attribute("src") or ""
        if src.startswith("http") and any(k in src.lower() for k in ("amerpol", "photo", "lot", "img")):
            if src not in listing.photos:
                listing.photos.append(src)
