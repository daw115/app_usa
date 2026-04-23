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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        kwargs = {}
        if state_file.exists():
            kwargs["storage_state"] = str(state_file)
        context = await browser.new_context(**kwargs)
        page = await context.new_page()
        try:
            await page.goto(AMERPOL_SEARCH_TPL.format(q=q), wait_until="domcontentloaded", timeout=30000)
            await jitter()
            cards = await page.query_selector_all("a[href*='/samochod/'], article a[href*='/lot/']")
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
                    log.debug("amerpol card parse failed: %s", e)

            for listing in results:
                try:
                    await page.goto(listing.source_url, wait_until="domcontentloaded", timeout=30000)
                    await jitter()
                    await _enrich_detail(page, listing)
                except Exception as e:
                    log.debug("amerpol detail fetch failed for %s: %s", listing.source_url, e)
        finally:
            await context.close()
            await browser.close()
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
