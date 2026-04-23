from __future__ import annotations

import logging
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from backend.config import config
from backend.services.scrapers.base import ScrapedListing, SearchCriteria

log = logging.getLogger(__name__)

COPART_SEARCH_TPL = "https://www.copart.com/lotSearchResults/?query={query}"


def _build_query(c: SearchCriteria) -> str:
    parts = [p for p in (c.make, c.model) if p]
    return quote(" ".join(parts) or "cars")


async def search(criteria: SearchCriteria) -> list[ScrapedListing]:
    """Scrape Copart using ScraperAPI (bypasses headless detection)"""
    if not config.scraperapi_key:
        log.warning("ScraperAPI key not configured - skipping Copart")
        return []

    results: list[ScrapedListing] = []
    url = COPART_SEARCH_TPL.format(query=_build_query(criteria))

    # ScraperAPI endpoint
    api_url = f"http://api.scraperapi.com?api_key={config.scraperapi_key}&url={quote(url)}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(api_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find lot links
            lot_links = soup.find_all('a', href=lambda x: x and '/lot/' in x)
            seen_urls = set()

            for link in lot_links[:criteria.max_results]:
                href = link.get('href', '')
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                if href.startswith('/'):
                    href = f"https://www.copart.com{href}"

                # Extract title from URL
                parts = href.split('/')
                title = parts[5].replace('-', ' ').title() if len(parts) >= 6 else f"Copart Lot {parts[4] if len(parts) > 4 else ''}"

                results.append(ScrapedListing(
                    source="copart",
                    source_url=href,
                    title=title,
                ))

            # Enrich with details
            for listing in results:
                try:
                    detail_url = f"http://api.scraperapi.com?api_key={config.scraperapi_key}&url={quote(listing.source_url)}"
                    detail_response = await client.get(detail_url)
                    detail_response.raise_for_status()
                    detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

                    # VIN
                    vin_el = detail_soup.find(attrs={'data-uname': 'lotdetailVinvalue'})
                    if vin_el:
                        listing.vin = vin_el.get_text(strip=True)[:17]

                    # Photos
                    imgs = detail_soup.find_all('img', src=lambda x: x and 'cs.copart.com' in x and 'lpp' in x)
                    for img in imgs[:15]:
                        src = img.get('src', '')
                        if src:
                            full_src = src.replace('_thb.jpg', '_ful.jpg').replace('_hrs.jpg', '_ful.jpg')
                            if full_src not in listing.photos:
                                listing.photos.append(full_src)
                except Exception as e:
                    log.debug(f"Failed to enrich {listing.source_url}: {e}")

        except Exception as e:
            log.error(f"ScraperAPI request failed: {e}")

    return results
