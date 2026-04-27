"""Google Maps Places API adapter.

Uses Text Search → returns up to 60 results across 3 pages (next_page_token).
Then Place Details for the fields the scorer / DB needs.

Docs: https://developers.google.com/maps/documentation/places/web-service/search-text
"""
import asyncio
import logging
from collections.abc import AsyncIterator

import httpx

from prospect_agent.models import Lead, Niche
from prospect_agent.scoring import search_query_for
from prospect_agent.settings import settings

log = logging.getLogger(__name__)

PLACES_BASE = "https://maps.googleapis.com/maps/api/place"


async def discover(niche: Niche, city: str) -> AsyncIterator[Lead]:
    """Yield Lead objects for one niche × city query, up to max_results_per_query."""
    if not settings.google_maps_api_key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set")

    query = search_query_for(niche, city)
    log.info("Discovering: %s", query)

    seen_place_ids: set[str] = set()
    next_token: str | None = None
    fetched = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        while fetched < settings.max_results_per_query:
            params: dict[str, str] = {
                "key": settings.google_maps_api_key,
                "query": query,
                "region": settings.country.lower(),
            }
            if next_token:
                params["pagetoken"] = next_token

            r = await client.get(f"{PLACES_BASE}/textsearch/json", params=params)
            r.raise_for_status()
            data = r.json()

            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                log.error("Places textsearch error: %s — %s", status, data.get("error_message"))
                break
            if status == "ZERO_RESULTS":
                break

            for place in data.get("results", []):
                pid = place.get("place_id")
                if not pid or pid in seen_place_ids:
                    continue
                seen_place_ids.add(pid)
                fetched += 1
                if fetched > settings.max_results_per_query:
                    return

                lead = await _enrich(client, place, niche=niche, city=city)
                yield lead

                # Politeness
                await asyncio.sleep(settings.request_delay_ms / 1000)

            next_token = data.get("next_page_token")
            if not next_token:
                break
            # Google requires a short delay before the next_page_token becomes valid
            await asyncio.sleep(2)


async def _enrich(client: httpx.AsyncClient, place: dict, *, niche: Niche, city: str) -> Lead:
    """Augment a textsearch result with Place Details (phone, website)."""
    pid = place["place_id"]
    fields = "name,formatted_phone_number,website,formatted_address,geometry"
    try:
        r = await client.get(
            f"{PLACES_BASE}/details/json",
            params={"key": settings.google_maps_api_key, "place_id": pid, "fields": fields},
        )
        r.raise_for_status()
        details = r.json().get("result", {})
    except Exception as exc:  # noqa: BLE001
        log.warning("details fetch failed for %s: %s", pid, exc)
        details = {}

    geom = (place.get("geometry") or {}).get("location") or {}
    return Lead(
        source="google_maps",
        google_place_id=pid,
        niche=niche,
        geo_city=city,
        geo_country=settings.country,
        business_name=place.get("name") or details.get("name") or "",
        business_address=place.get("formatted_address") or details.get("formatted_address"),
        business_lat=geom.get("lat"),
        business_lng=geom.get("lng"),
        business_rating=place.get("rating"),
        business_review_count=place.get("user_ratings_total"),
        business_phone=details.get("formatted_phone_number"),
        business_website_url=details.get("website"),
        metadata={"types": place.get("types", [])},
    )
