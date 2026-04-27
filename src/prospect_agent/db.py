"""Postgres client for prospect-agent."""
import json
import logging

import asyncpg

from prospect_agent.models import Lead
from prospect_agent.settings import settings

log = logging.getLogger(__name__)


class DB:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB not connected — call connect() first")
        return self._pool

    async def connect(self) -> None:
        if not settings.aicore_db_url:
            raise RuntimeError("AICORE_DB_URL not set")
        self._pool = await asyncpg.create_pool(
            settings.aicore_db_url, min_size=1, max_size=3, init=_init_connection,
        )

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def upsert_lead(self, lead: Lead) -> str:
        """Insert or update on (google_place_id). Preserves status if row exists."""
        row = await self.pool.fetchrow(
            """
            INSERT INTO leads
              (source, google_place_id, niche, geo_city, geo_country,
               business_name, business_address, business_lat, business_lng,
               business_rating, business_review_count, business_phone,
               business_website_url,
               website_https, website_mobile_score, website_has_booking,
               fit_score, score_factors, status, metadata)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                    $17,$18,$19,$20)
            ON CONFLICT (google_place_id)
              WHERE google_place_id IS NOT NULL
              DO UPDATE SET
                business_name = EXCLUDED.business_name,
                business_address = EXCLUDED.business_address,
                business_rating = EXCLUDED.business_rating,
                business_review_count = EXCLUDED.business_review_count,
                business_phone = COALESCE(EXCLUDED.business_phone, leads.business_phone),
                business_website_url = COALESCE(
                  EXCLUDED.business_website_url, leads.business_website_url
                ),
                website_https = EXCLUDED.website_https,
                website_mobile_score = EXCLUDED.website_mobile_score,
                website_has_booking = EXCLUDED.website_has_booking,
                fit_score = EXCLUDED.fit_score,
                score_factors = EXCLUDED.score_factors,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id
            """,
            lead.source, lead.google_place_id, lead.niche, lead.geo_city, lead.geo_country,
            lead.business_name, lead.business_address, lead.business_lat, lead.business_lng,
            lead.business_rating, lead.business_review_count, lead.business_phone,
            lead.business_website_url,
            lead.website.https, lead.website.mobile_score, lead.website.has_booking,
            lead.fit_score, lead.score_factors, lead.status, lead.metadata,
        )
        return str(row["id"])


    # ─── Chain dedup ────────────────────────────────────────────────────────

    async def all_leads_for_chain_detection(self) -> list[dict]:
        """Minimal columns the chain detector needs."""
        rows = await self.pool.fetch(
            """
            SELECT id::text AS id, business_name, business_website_url,
                   business_review_count, niche, geo_country
            FROM leads
            """,
        )
        return [dict(r) for r in rows]

    async def apply_chain_assignments(self, assignments: dict[str, dict]) -> int:
        """Update chain_name + chain_role for each lead. Returns rows touched."""
        if not assignments:
            return 0
        async with self.pool.acquire() as conn:
            await conn.executemany(
                """
                UPDATE leads
                   SET chain_name = $2,
                       chain_role = $3,
                       updated_at = NOW()
                 WHERE id = $1::uuid
                """,
                [(lead_id, v["chain_name"], v["chain_role"])
                 for lead_id, v in assignments.items()],
            )
        return len(assignments)


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


db = DB()
