from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx
from anthropic import Anthropic

from backend.config import config
from backend.services.cache import cache_key_for_ai_analysis, get_cache

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


SYSTEM_PROMPT = """You are an expert US salvage-auction car inspector.
You analyze Copart/IAAI/Amerpol listings for a dealer who imports damaged cars
from the US to Poland. Your job: from photos + listing text, estimate damage
severity, identify red flags, and give a realistic USD repair cost range for
a Polish body shop (labor ~30 USD/h, parts mostly aftermarket or US-sourced).

You MUST respond with a single JSON object and no other text. Schema:
{
  "damage_score": int 1-10,   // 1 = cosmetic, 10 = total loss, rebuilt title
  "primary_damage_areas": [string],
  "structural_damage": bool,
  "airbags_deployed": bool,
  "frame_damage_risk": bool,
  "flood_water_damage_risk": bool,
  "interior_damage": bool,
  "repair_estimate_usd": {"low": number, "high": number},
  "repair_notes": string,     // 1-3 sentences, what the shop will have to do
  "red_flags": [string],      // things that could kill the deal
  "worth_buying": bool,
  "confidence": "low" | "medium" | "high"
}

Be conservative with estimates — it's better to overestimate repair costs
than to surprise the client later. If photos are insufficient, set
confidence="low" and widen the repair range."""


async def _fetch_image_as_base64(url: str, http: httpx.AsyncClient) -> tuple[str, str] | None:
    try:
        r = await http.get(url, timeout=15.0)
        r.raise_for_status()
        media_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if not media_type.startswith("image/"):
            media_type = "image/jpeg"
        return media_type, base64.standard_b64encode(r.content).decode("ascii")
    except Exception as e:
        log.warning("failed to fetch image %s: %s", url, e)
        return None


def _build_listing_context(listing_data: dict[str, Any]) -> str:
    keys = ["title", "year", "make", "model", "mileage", "damage_primary",
            "damage_secondary", "location", "current_bid_usd", "buy_now_usd", "vin"]
    lines = []
    for k in keys:
        v = listing_data.get(k)
        if v not in (None, "", 0):
            lines.append(f"- {k}: {v}")
    return "\n".join(lines) or "(no metadata)"


async def analyze_listing(
    listing_data: dict[str, Any],
    photo_urls: list[str],
    max_photos: int = 6,
) -> dict[str, Any]:
    # Check cache first
    cache = get_cache()
    cache_key = cache_key_for_ai_analysis({"vin": listing_data.get("vin", ""), "photos": photo_urls[:max_photos]})
    cached = cache.get(cache_key)
    if cached:
        log.info(f"AI analysis cache hit for VIN {listing_data.get('vin', 'unknown')}")
        return cached

    async with httpx.AsyncClient() as http:
        images: list[dict[str, Any]] = []
        for url in photo_urls[:max_photos]:
            fetched = await _fetch_image_as_base64(url, http)
            if fetched:
                media_type, data = fetched
                images.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                })

    context = _build_listing_context(listing_data)
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": f"Listing metadata:\n{context}\n\nPhotos follow. Analyze and return JSON only."}
    ]
    user_content.extend(images)

    client = _anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_content}],
    )

    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        log.error("failed to parse analyzer JSON: %s -- %s", e, text[:500])
        parsed = {
            "damage_score": 5,
            "primary_damage_areas": [],
            "structural_damage": False,
            "airbags_deployed": False,
            "frame_damage_risk": False,
            "flood_water_damage_risk": False,
            "interior_damage": False,
            "repair_estimate_usd": {"low": 0, "high": 0},
            "repair_notes": "(parsing failure — raw: " + text[:200] + ")",
            "red_flags": ["analyzer failed to parse response"],
            "worth_buying": False,
            "confidence": "low",
        }

    parsed["_usage"] = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
        "cache_read": getattr(resp.usage, "cache_read_input_tokens", 0),
        "cache_write": getattr(resp.usage, "cache_creation_input_tokens", 0),
    }

    # Cache result for 24 hours
    cache.set(cache_key, parsed, ttl_seconds=86400)
    log.info(f"AI analysis cached for VIN {listing_data.get('vin', 'unknown')}")

    return parsed
