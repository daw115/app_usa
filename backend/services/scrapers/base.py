from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import ROOT

PROFILES_DIR = ROOT / "playwright_profiles"
PROFILES_DIR.mkdir(exist_ok=True)


@dataclass
class SearchCriteria:
    make: str = ""
    model: str = ""
    year_from: int | None = None
    year_to: int | None = None
    budget_pln: int | None = None
    mileage_max: int | None = None
    damage_tolerance: str = "light"
    max_results: int = 20


@dataclass
class ScrapedListing:
    source: str
    source_url: str
    vin: str = ""
    title: str = ""
    year: int | None = None
    make: str = ""
    model: str = ""
    mileage: int | None = None
    damage_primary: str = ""
    damage_secondary: str = ""
    location: str = ""
    auction_date: str = ""
    current_bid_usd: float | None = None
    buy_now_usd: float | None = None
    photos: list[str] = field(default_factory=list)


async def jitter(min_s: float = 1.5, max_s: float = 4.0) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


def storage_state_path(name: str) -> Path:
    return PROFILES_DIR / f"{name}.json"


def budget_pln_to_usd_cap(budget_pln: int | None, usd_pln_rate: float, headroom_pct: float = 0.45) -> int | None:
    """Rough cap for the auction price — budget minus expected taxes/transport/margin."""
    if not budget_pln:
        return None
    after_headroom = budget_pln * (1.0 - headroom_pct)
    return max(500, int(after_headroom / max(usd_pln_rate, 1.0)))
