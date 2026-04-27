# prospect-agent

Phase 6a — discovers Malaysian restaurants and clinics that need a website, scores fit, and lands them in the `leads` table.

For system context, read [`infra-core/docs/PHASE-6-PLAN.md`](https://github.com/1305a001-ctrl/infra-core/blob/main/docs/PHASE-6-PLAN.md).

## What it does

For each `(niche × city)`:
1. Google Maps **Text Search** for "<niche-term> in <city>" → up to 60 places per query
2. **Place Details** for each result (phone, website)
3. If website present → fetch homepage and detect HTTPS, mobile-friendly markers, booking widget
4. Score 0..1 (higher = better fit; bigger gap between current site and what we'd build)
5. Upsert into `leads` (dedupe on `google_place_id`, preserves `status` if already moved past `new`)

One-shot — no daemon. Re-run on schedule or manually.

## Niches + queries

| Niche | Google Maps query |
|---|---|
| `restaurant` | "restaurant in <city>" |
| `clinic_dental` | "dental clinic in <city>" |
| `clinic_medical` | "medical clinic in <city>" |
| `clinic_beauty` | "beauty clinic in <city>" |

## Default cities (Malaysia)

KL, Petaling Jaya, Subang Jaya, Penang, Johor Bahru, Ipoh, Malacca. Override with `CITIES` env var (comma-separated).

## Score breakdown (factors are additive, capped at 1.0)

| Factor | +score | Trigger |
|---|---|---|
| `no_website` | 0.45 | Google Maps shows no website |
| `no_https` | 0.15 | Website exists but HTTP |
| `poor_mobile` | 0.15 | Heuristic mobile_score < 60 |
| `no_booking` | 0.10 | No Cal.com / Calendly / OpenTable / setmore / etc detected |
| `rating_in_band` | 0.05 | Google rating ∈ [3.5, 4.5] (cares + room to improve) |
| `active_business` | 0.05 | ≥50 Google reviews |
| `clinic_aov_bonus` | 0.05 | Niche starts with `clinic_` (higher AOV than restaurants) |

## Module map

```
src/prospect_agent/
├── main.py               # one-shot orchestrator
├── settings.py           # env: API key, niches, cities, request delays
├── db.py                 # asyncpg pool + JSONB codec; upsert_lead with ON CONFLICT
├── models.py             # Lead + WebsiteAnalysis pydantic types
├── scoring.py            # PURE — score_lead, search_query_for (covered by tests)
└── sources/
    ├── google_maps.py    # Places Text Search + Place Details
    └── website_scraper.py # Lightweight homepage analysis (https, mobile, booking)
```

## Wire-up

1. Get a Google Maps API key with **Places API** enabled (https://console.cloud.google.com/apis/library/places-backend.googleapis.com). Free tier covers ~10k req/mo.
2. Apply migration:
   ```bash
   cat migrations/005_phase6_leads.sql | ssh ai-primary 'sudo docker exec -i postgres psql -U benadmin -d aicore'
   ```
3. Set env in `/srv/secrets/prospect-agent.env` (Postgres URL, Google Maps key, optional niches/cities overrides).
4. Run:
   ```bash
   docker compose -f infra-core/compose/prospect-agent/docker-compose.yml run --rm prospect-agent
   ```

## Tests

```bash
pip install -e '.[dev]'
pytest -q
```

`tests/test_scoring.py` — 9 cases covering each factor + composite + niche-query mapping.

## What's next (Phase 6 roadmap)

- **6a v0.2** (this repo): add Hunter.io domain search to enrich `business_email` for top-fit leads
- **6b**: outreach-agent reads `leads` table and drafts cold emails (subject to your approval)
- **6c**: demo-builder generates a Next.js demo when `status='replied'`
- **6d** + **6e**: contracts → production builds → maintenance

See [PHASE-6-PLAN.md](https://github.com/1305a001-ctrl/infra-core/blob/main/docs/PHASE-6-PLAN.md).
