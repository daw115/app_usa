"""Per-source daily rate limit for scrapers.

Tracks every scraper invocation in `scraper_run` table. Refuses new scrapes
when the rolling 24h count for a source exceeds `config.scraper_daily_limit`.

The goal is to avoid getting accounts banned on the auction sites.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, func, select

from backend.config import config
from backend.db import engine
from backend.models import ScraperRun, Source

log = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    def __init__(self, source: str, count: int, limit: int):
        self.source = source
        self.count = count
        self.limit = limit
        super().__init__(
            f"Scraper '{source}' rate limit exceeded: {count}/{limit} in last 24h"
        )


def count_recent(source: Source, hours: int = 24) -> int:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    with Session(engine) as s:
        result = s.exec(
            select(func.count(ScraperRun.id)).where(
                ScraperRun.source == source,
                ScraperRun.started_at >= cutoff,
            )
        ).one()
        return int(result or 0)


def check_and_reserve(source: Source, inquiry_id: Optional[int] = None) -> ScraperRun:
    """Check rate limit and create a ScraperRun row reserving a slot.

    Returns the created ScraperRun (caller should update it with result via
    `mark_complete`). Raises RateLimitExceeded if over limit.
    """
    count = count_recent(source)
    limit = config.scraper_daily_limit
    if count >= limit:
        log.warning("Rate limit hit for %s: %d/%d in last 24h", source, count, limit)
        raise RateLimitExceeded(source.value, count, limit)

    with Session(engine) as s:
        run = ScraperRun(source=source, inquiry_id=inquiry_id)
        s.add(run)
        s.commit()
        s.refresh(run)
        log.info("Scraper %s slot reserved (run_id=%s, %d/%d used)",
                 source.value, run.id, count + 1, limit)
        return run


def mark_complete(run_id: int, *, success: bool, results_count: int = 0,
                  error: str = "") -> None:
    with Session(engine) as s:
        run = s.get(ScraperRun, run_id)
        if not run:
            return
        run.success = success
        run.results_count = results_count
        run.error = error[:500]
        s.add(run)
        s.commit()


def usage_summary() -> dict[str, dict]:
    """Return current usage per source for the dashboard."""
    out: dict[str, dict] = {}
    for src in Source:
        count = count_recent(src)
        out[src.value] = {
            "used": count,
            "limit": config.scraper_daily_limit,
            "remaining": max(0, config.scraper_daily_limit - count),
        }
    return out
