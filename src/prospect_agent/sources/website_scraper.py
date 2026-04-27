"""Lightweight website analysis to enrich a Lead.

Fetches the homepage and extracts a few signals the scorer cares about:
  - https — was the redirected URL https?
  - has_booking — search the HTML for a booking link / widget marker
  - mobile_score — *very* rough heuristic (presence of viewport meta + responsive CSS hints).
                   Not a Lighthouse score; skip if you want true accuracy.
"""
import logging
import re

import httpx

from prospect_agent.models import WebsiteAnalysis
from prospect_agent.settings import settings

log = logging.getLogger(__name__)

BOOKING_MARKERS = re.compile(
    r"calendly\.com|cal\.com/|squareup\.com/appointments|setmore\.com|"
    r"opentable\.com|book[\-_]?(now|online|appointment)|reservation",
    re.IGNORECASE,
)


async def analyze(url: str) -> WebsiteAnalysis:
    if not url:
        return WebsiteAnalysis()
    try:
        async with httpx.AsyncClient(
            timeout=settings.website_fetch_timeout_seconds, follow_redirects=True,
        ) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 prospect-agent"})
        final_url = str(r.url)
        body = r.text or ""

        return WebsiteAnalysis(
            https=final_url.startswith("https://"),
            has_booking=bool(BOOKING_MARKERS.search(body)),
            mobile_score=_mobile_heuristic(body),
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("website analysis failed for %s: %s", url, exc)
        return WebsiteAnalysis()


def _mobile_heuristic(html: str) -> int:
    """Crude 0-100 score based on responsive markers. Not a real Lighthouse audit."""
    score = 0
    if 'name="viewport"' in html.lower():
        score += 40
    if "@media" in html.lower() or "max-width:" in html.lower():
        score += 30
    if 'class="container"' in html.lower() or "rem;" in html.lower():
        score += 15
    if "tailwind" in html.lower() or "bootstrap" in html.lower():
        score += 15
    return min(score, 100)
