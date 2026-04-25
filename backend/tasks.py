from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlmodel import Session, select

from backend.config import config
from backend.db import engine
from backend.models import Inquiry, InquiryStatus, Listing, Report, Settings, Source
from backend.models import Source
from backend.services import analyzer, synthesizer
from backend.services.pricing import calculate, fetch_nbp_usd_rate
from backend.services.rate_limit import RateLimitExceeded, check_and_reserve, mark_complete
from backend.services.scrapers import amerpol, iaai
from backend.services.scrapers import copart_scraperapi as copart
from backend.services.scrapers.base import SearchCriteria, ScrapedListing
from backend.services.telegram_bot import notify_error, notify_report_ready

log = logging.getLogger(__name__)


def _get_settings(s: Session) -> Settings:
    row = s.exec(select(Settings).where(Settings.id == 1)).first()
    if not row:
        row = Settings(id=1)
        s.add(row)
        s.commit()
        s.refresh(row)
    return row


async def _refresh_usd_rate(s: Session) -> None:
    settings = _get_settings(s)
    if not settings.auto_usd_rate:
        return
    rate = await fetch_nbp_usd_rate()
    if rate and abs(rate - settings.usd_pln_rate) > 0.01:
        settings.usd_pln_rate = rate
        s.add(settings)
        s.commit()


def _criteria(inquiry: Inquiry) -> SearchCriteria:
    return SearchCriteria(
        make=inquiry.make,
        model=inquiry.model,
        year_from=inquiry.year_from,
        year_to=inquiry.year_to,
        budget_pln=inquiry.budget_pln,
        mileage_max=inquiry.mileage_max,
        damage_tolerance=inquiry.damage_tolerance.value,
        max_results=8,
    )


def _persist_scraped(s: Session, inquiry_id: int, items: list[ScrapedListing]) -> list[Listing]:
    saved: list[Listing] = []
    for item in items:
        listing = Listing(
            inquiry_id=inquiry_id,
            source=Source(item.source),
            source_url=item.source_url,
            vin=item.vin,
            title=item.title,
            year=item.year,
            make=item.make,
            model=item.model,
            mileage=item.mileage,
            damage_primary=item.damage_primary,
            damage_secondary=item.damage_secondary,
            location=item.location,
            auction_date=item.auction_date,
            current_bid_usd=item.current_bid_usd,
            buy_now_usd=item.buy_now_usd,
            photos_json=json.dumps(item.photos),
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        saved.append(listing)
    return saved


def _apply_analysis(listing: Listing, result: dict[str, Any], settings: Settings) -> None:
    repair = result.get("repair_estimate_usd") or {}
    low = repair.get("low")
    high = repair.get("high")
    listing.ai_damage_score = int(result.get("damage_score") or 0) or None
    listing.ai_repair_estimate_usd_low = float(low) if low is not None else None
    listing.ai_repair_estimate_usd_high = float(high) if high is not None else None
    listing.ai_notes = result.get("repair_notes", "")[:2000]
    listing.ai_raw_json = json.dumps(result, ensure_ascii=False)

    auction = listing.buy_now_usd or listing.current_bid_usd or 0.0
    breakdown = calculate(auction, low, high, settings)
    listing.total_cost_pln = breakdown.total_pln


def _rank(listings: list[Listing], inquiry: Inquiry) -> None:
    in_budget = [l for l in listings if l.total_cost_pln and (not inquiry.budget_pln or l.total_cost_pln <= inquiry.budget_pln * 1.1)]
    in_budget.sort(key=lambda l: (
        l.ai_damage_score or 10,
        l.total_cost_pln or float("inf"),
    ))
    for i, l in enumerate(in_budget[:5], start=1):
        l.recommended_rank = i
    for l in listings:
        if l not in in_budget[:5] and l.recommended_rank is None:
            l.excluded = True


async def run_search_pipeline(inquiry_id: int) -> None:
    log.info("run_search_pipeline inquiry=%s", inquiry_id)
    try:
        with Session(engine) as s:
            inquiry = s.get(Inquiry, inquiry_id)
            if not inquiry:
                return
            inquiry.status = InquiryStatus.searching
            s.add(inquiry)
            s.commit()
            await _refresh_usd_rate(s)
            criteria = _criteria(inquiry)

        # Parallel scraping with rate limiting + per-source timeout
        SCRAPER_TIMEOUT_S = 90  # hard cap per source (Playwright can hang)

        async def scrape_source(mod, source: Source):
            try:
                run = check_and_reserve(source, inquiry_id=inquiry_id)
            except RateLimitExceeded as e:
                log.warning("Skipping %s: %s", source.value, e)
                return []

            try:
                scraped = await asyncio.wait_for(
                    mod.search(criteria), timeout=SCRAPER_TIMEOUT_S
                )
                log.info("%s returned %d results", mod.__name__, len(scraped))
                mark_complete(run.id, success=True, results_count=len(scraped))
                return scraped
            except asyncio.TimeoutError:
                log.error("scraper %s timed out after %ss", mod.__name__, SCRAPER_TIMEOUT_S)
                mark_complete(run.id, success=False, error=f"timeout {SCRAPER_TIMEOUT_S}s")
                return []
            except Exception as e:
                log.exception("scraper %s failed: %s", mod.__name__, e)
                mark_complete(run.id, success=False, error=str(e))
                return []

        results = await asyncio.gather(
            scrape_source(amerpol, Source.amerpol),
            scrape_source(copart, Source.copart),
            scrape_source(iaai, Source.iaai),
        )
        all_scraped = [item for sublist in results for item in sublist]

        with Session(engine) as s:
            inquiry = s.get(Inquiry, inquiry_id)
            settings = _get_settings(s)
            saved = _persist_scraped(s, inquiry_id, all_scraped)
            inquiry.status = InquiryStatus.analyzing
            s.add(inquiry)
            s.commit()

        # Parallel AI analysis
        with Session(engine) as s:
            settings = _get_settings(s)
            listings = s.exec(select(Listing).where(Listing.inquiry_id == inquiry_id)).all()

            async def analyze_one(listing: Listing):
                photos = json.loads(listing.photos_json or "[]")
                if not photos:
                    return None
                listing_data = {
                    "title": listing.title,
                    "year": listing.year,
                    "make": listing.make,
                    "model": listing.model,
                    "mileage": listing.mileage,
                    "damage_primary": listing.damage_primary,
                    "damage_secondary": listing.damage_secondary,
                    "location": listing.location,
                    "current_bid_usd": listing.current_bid_usd,
                    "buy_now_usd": listing.buy_now_usd,
                    "vin": listing.vin,
                }
                try:
                    result = await asyncio.wait_for(
                        analyzer.analyze_listing(listing_data, photos),
                        timeout=config.ai_timeout_seconds,
                    )
                    return (listing, result)
                except asyncio.TimeoutError:
                    log.error("analyzer timeout (%ss) for listing %s",
                              config.ai_timeout_seconds, listing.id)
                    return None
                except Exception as e:
                    log.exception("analyzer failed for listing %s: %s", listing.id, e)
                    return None

            # Analyze all listings in parallel
            analysis_results = await asyncio.gather(*[analyze_one(l) for l in listings])

            # Apply results
            for result in analysis_results:
                if result:
                    listing, analysis = result
                    _apply_analysis(listing, analysis, settings)
                    s.add(listing)
            s.commit()

            listings = s.exec(select(Listing).where(Listing.inquiry_id == inquiry_id)).all()
            _rank(listings, s.get(Inquiry, inquiry_id))
            for l in listings:
                s.add(l)
            s.commit()

            inquiry = s.get(Inquiry, inquiry_id)
            inquiry.status = InquiryStatus.ready
            s.add(inquiry)
            s.commit()

        log.info("pipeline finished inquiry=%s", inquiry_id)
    except Exception as e:
        log.exception("pipeline failed inquiry=%s: %s", inquiry_id, e)
        await notify_error(inquiry_id, str(e))


async def generate_report(inquiry_id: int) -> int:
    with Session(engine) as s:
        inquiry = s.get(Inquiry, inquiry_id)
        if not inquiry:
            raise ValueError("inquiry not found")
        listings = s.exec(select(Listing).where(Listing.inquiry_id == inquiry_id)).all()
        subject, html = synthesizer.synthesize_report(inquiry, listings)
        selected = [l.id for l in listings if l.recommended_rank is not None]
        report = Report(
            inquiry_id=inquiry_id,
            subject=subject,
            html_body=html,
            selected_listing_ids=json.dumps(selected),
        )
        s.add(report)
        s.commit()
        s.refresh(report)
        report_id = report.id
    await notify_report_ready(report_id)
    return report_id
