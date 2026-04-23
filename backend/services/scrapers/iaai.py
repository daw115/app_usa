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

IAAI_SEARCH_TPL = "https://www.iaai.com/Search?Keyword={q}"


async def search(criteria: SearchCriteria) -> list[ScrapedListing]:
    state_file = storage_state_path("iaai")
    if not state_file.exists():
        log.warning("IAAI storage_state missing at %s — skipping.", state_file)
        return []

    q = quote(f"{criteria.make} {criteria.model}".strip() or "cars")
    results: list[ScrapedListing] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()
        try:
            await page.goto(IAAI_SEARCH_TPL.format(q=q), wait_until="domcontentloaded", timeout=30000)
            await jitter()
            try:
                await page.wait_for_selector("div.table-row-inner", timeout=15000)
            except Exception:
                log.warning("IAAI: no results rows found")
                return results
            cards = await page.query_selector_all("div.table-row-inner")
            for card in cards[: criteria.max_results]:
                try:
                    link_el = await card.query_selector("a.heading-7")
                    if not link_el:
                        continue
                    href = await link_el.get_attribute("href") or ""
                    if href.startswith("/"):
                        href = "https://www.iaai.com" + href
                    title = (await link_el.inner_text()).strip()
                    results.append(ScrapedListing(
                        source="iaai",
                        source_url=href,
                        title=title,
                    ))
                except Exception as e:
                    log.debug("iaai row parse failed: %s", e)

            for listing in results:
                try:
                    await page.goto(listing.source_url, wait_until="domcontentloaded", timeout=30000)
                    await jitter()
                    await _enrich_detail(page, listing)
                except Exception as e:
                    log.debug("iaai detail fetch failed for %s: %s", listing.source_url, e)
        finally:
            await context.close()
            await browser.close()
    return results


async def _enrich_detail(page, listing: ScrapedListing) -> None:
    vin_el = await page.query_selector("[data-testid='vehicle-vin'], .heading-details-value")
    if vin_el:
        listing.vin = (await vin_el.inner_text()).strip().split()[0][:17]
    imgs = await page.query_selector_all("img[src*='vis.iaai.com'], img.gallery-img")
    for img in imgs[:10]:
        src = await img.get_attribute("src")
        if src and src.startswith("http"):
            listing.photos.append(src)
