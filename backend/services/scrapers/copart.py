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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()
        try:
            url = COPART_SEARCH_TPL.format(query=_build_query(criteria))
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await jitter()
            await page.wait_for_timeout(3000)

            lot_links = await page.query_selector_all("a[href*='/lot/']")
            seen_urls = set()
            log.info(f"Found {len(lot_links)} lot links on Copart search page")

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

                    # Extract title from URL: /lot/99885295/2013-bmw-x5-xdrive35i-nj-glassboro-east
                    parts = href.split("/")
                    if len(parts) >= 6:
                        title = parts[5].replace("-", " ").title()
                    else:
                        title = f"Copart Lot {parts[4] if len(parts) > 4 else ''}"
                        log.debug(f"Short URL, parts={len(parts)}: {href}")

                    log.debug(f"Adding listing: {title} from {href}")
                    results.append(ScrapedListing(
                        source="copart",
                        source_url=href,
                        title=title,
                    ))
                except Exception as e:
                    log.debug("copart link parse failed: %s", e)

            for listing in results:
                try:
                    await page.goto(listing.source_url, wait_until="domcontentloaded", timeout=30000)
                    await jitter()
                    await _enrich_detail(page, listing)
                except Exception as e:
                    log.debug("copart detail fetch failed for %s: %s", listing.source_url, e)
        finally:
            await context.close()
            await browser.close()
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
    for sel in ["[data-uname='lotdetailVinvalue']", "span:has-text('VIN')", ".vin-number"]:
        vin_el = await page.query_selector(sel)
        if vin_el:
            listing.vin = (await vin_el.inner_text()).strip()[:17]
            break

    # Photos
    await page.wait_for_timeout(2000)
    imgs = await page.query_selector_all("img")
    for img in imgs[:30]:
        src = await img.get_attribute("src")
        if src and "cs.copart.com" in src and "lpp" in src:
            # Convert to full size
            full_src = src.replace("_thb.jpg", "_ful.jpg").replace("_hrs.jpg", "_ful.jpg")
            if full_src not in listing.photos:
                listing.photos.append(full_src)


def is_configured() -> bool:
    return storage_state_path("copart").exists() or bool(config.copart_username and config.copart_password)
