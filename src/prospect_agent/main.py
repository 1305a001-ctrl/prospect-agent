"""prospect-agent — one-shot.

For each (niche × city) in settings, search Google Maps, optionally enrich
each result with a website analysis, score, and upsert into the `leads` table.

Idempotent: re-running updates fit_score / website fields and preserves
the existing `status` (so a lead manually moved to 'qualified' isn't
reset to 'new' on re-discovery).
"""
import asyncio
import logging

import sentry_sdk

from prospect_agent.chains import detect_chains
from prospect_agent.db import db
from prospect_agent.models import Lead
from prospect_agent.scoring import score_lead
from prospect_agent.settings import settings
from prospect_agent.sources import google_maps, website_scraper

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.0)


async def discover_and_score() -> dict:
    totals = {"discovered": 0, "scored": 0, "upserted": 0, "errors": 0}

    for niche in settings.niche_list:
        for city in settings.city_list:
            try:
                async for lead in google_maps.discover(niche, city):  # type: ignore[arg-type]
                    totals["discovered"] += 1

                    if settings.enrich_websites and lead.business_website_url:
                        try:
                            lead.website = await website_scraper.analyze(
                                lead.business_website_url,
                            )
                        except Exception:
                            log.exception("website analysis failed")

                    fit, factors = score_lead(lead)
                    lead.fit_score = fit
                    lead.score_factors = factors
                    totals["scored"] += 1

                    try:
                        await db.upsert_lead(lead)
                        totals["upserted"] += 1
                    except Exception:
                        log.exception("upsert failed for %s", lead.business_name)
                        totals["errors"] += 1
            except Exception:
                log.exception("discovery failed for niche=%s city=%s", niche, city)
                totals["errors"] += 1

    return totals


async def detect_and_apply_chains() -> int:
    """Run chain detection across ALL leads (newly-discovered + historical)
    and apply chain_name + chain_role updates. Idempotent."""
    rows = await db.all_leads_for_chain_detection()
    assignments = detect_chains(rows)
    n = await db.apply_chain_assignments(assignments)
    parents = sum(1 for v in assignments.values() if v["chain_role"] == "parent")
    branches = sum(1 for v in assignments.values() if v["chain_role"] == "branch")
    log.info("Chain detection: %d leads, %d parents, %d branches", n, parents, branches)
    return n


async def main() -> None:
    _setup_logging()
    log.info(
        "prospect-agent starting (niches=%s, cities=%s)",
        settings.niche_list, settings.city_list,
    )
    if not settings.google_maps_api_key:
        log.error("GOOGLE_MAPS_API_KEY not set — running chain detection on existing rows only")
        await db.connect()
        try:
            await detect_and_apply_chains()
        finally:
            await db.close()
        return
    await db.connect()
    try:
        totals = await discover_and_score()
        log.info("Discovery done: %s", totals)
        await detect_and_apply_chains()
    finally:
        await db.close()


# silence unused-import in main.py
_ = Lead


if __name__ == "__main__":
    asyncio.run(main())
