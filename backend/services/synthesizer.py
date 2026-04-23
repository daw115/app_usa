from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic

from backend.config import config
from backend.models import Inquiry, Listing

log = logging.getLogger(__name__)

_client: Anthropic | None = None


def _anthropic() -> Anthropic:
    global _client
    if _client is None:
        kwargs = {"api_key": config.anthropic_api_key}
        if config.anthropic_base_url:
            kwargs["base_url"] = config.anthropic_base_url
        _client = Anthropic(**kwargs)
    return _client


SYSTEM_PROMPT = """You are a senior car import advisor writing a final
recommendation email to a Polish client. The dealer (the sender) imports
cars from US salvage auctions (Copart, IAAI, Amerpol).

Output a polished Polish-language HTML email body (no <html>/<head> —
just the inner content). Structure:

1. A warm, personal opening (1-2 short paragraphs). Mention that you spent
   time reviewing multiple auctions to find the best matches. Never say
   "AI" or "automatycznie wygenerowane".
2. A responsive <table> with columns: Rok/Model, Przebieg, Szkoda,
   Koszt całkowity (PLN), Link. Include 3-5 recommended cars, ordered by
   the dealer's ranking.
3. For each car, a short paragraph underneath the table summarizing
   strengths, concerns, and repair scope in plain Polish.
4. A final recommendation: which one you'd personally choose and why.
5. CTA: "Proszę o telefon do potwierdzenia wyboru — auto może zniknąć
   z aukcji w ciągu kilku dni".

Tone: professional, confident, concrete. Use <strong> for prices.
Use inline styles for table borders only — keep it simple and email-safe.
No disclaimers about automation. No Markdown, only HTML."""


def _compact_listing(l: Listing) -> dict[str, Any]:
    return {
        "id": l.id,
        "source": l.source,
        "url": l.source_url,
        "vin": l.vin,
        "title": l.title,
        "year": l.year,
        "make": l.make,
        "model": l.model,
        "mileage_km": l.mileage,
        "damage_primary": l.damage_primary,
        "damage_secondary": l.damage_secondary,
        "location": l.location,
        "auction_date": l.auction_date,
        "current_bid_usd": l.current_bid_usd,
        "buy_now_usd": l.buy_now_usd,
        "ai_damage_score": l.ai_damage_score,
        "ai_repair_estimate_usd": {
            "low": l.ai_repair_estimate_usd_low,
            "high": l.ai_repair_estimate_usd_high,
        },
        "ai_notes": l.ai_notes,
        "total_cost_pln": l.total_cost_pln,
        "recommended_rank": l.recommended_rank,
    }


def synthesize_report(inquiry: Inquiry, listings: list[Listing]) -> tuple[str, str]:
    ranked = sorted(
        [l for l in listings if not l.excluded and l.recommended_rank is not None],
        key=lambda x: x.recommended_rank or 999,
    )[:5]

    payload = {
        "client": {
            "name": inquiry.client_name,
            "requirements": {
                "make": inquiry.make,
                "model": inquiry.model,
                "year_from": inquiry.year_from,
                "year_to": inquiry.year_to,
                "budget_pln": inquiry.budget_pln,
                "mileage_max": inquiry.mileage_max,
                "body_type": inquiry.body_type,
                "fuel": inquiry.fuel,
                "transmission": inquiry.transmission,
                "damage_tolerance": inquiry.damage_tolerance,
                "extra_notes": inquiry.extra_notes,
            },
        },
        "recommended_cars": [_compact_listing(l) for l in ranked],
    }

    client = _anthropic()
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Przygotuj email z ofertą dla klienta na podstawie tych danych. "
                "Zwróć tylko gotowy HTML (bez <html>, <head>, <body>).\n\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
            ),
        }],
    )
    html = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if html.startswith("```"):
        html = html.strip("`")
        if html.startswith("html"):
            html = html[4:].strip()

    first_car = ranked[0] if ranked else None
    if first_car:
        subj = f"Oferta aut z USA — {first_car.year or ''} {first_car.make} {first_car.model}".strip()
    else:
        subj = f"Oferta aut z USA dla {inquiry.client_name}"

    return subj, html
