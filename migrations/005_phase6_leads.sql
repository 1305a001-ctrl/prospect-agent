-- Phase 6 — Phase6 leads table.
-- Owned by prospect-agent (writes); read by control-plane /leads page.
-- Run: cat migrations/005_phase6_leads.sql | ssh ai-primary "sudo docker exec -i postgres psql -U benadmin -d aicore"

CREATE TABLE IF NOT EXISTS leads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Source / identity
  source TEXT NOT NULL,                  -- 'google_maps', 'manual', etc.
  google_place_id TEXT,                  -- canonical id when source=google_maps
  niche TEXT NOT NULL,                   -- 'restaurant','clinic_dental','clinic_medical','clinic_beauty'
  geo_city TEXT,                         -- 'Kuala Lumpur', 'Penang', 'Johor Bahru'
  geo_country TEXT NOT NULL DEFAULT 'MY',

  -- Business
  business_name TEXT NOT NULL,
  business_address TEXT,
  business_lat REAL,
  business_lng REAL,
  business_rating REAL,                  -- Google rating, 1-5
  business_review_count INTEGER,         -- number of reviews
  business_phone TEXT,
  business_website_url TEXT,

  -- Website analysis (set by website_scraper if business_website_url present)
  website_https BOOLEAN,
  website_mobile_score INTEGER,          -- 0-100 (Lighthouse-ish)
  website_has_booking BOOLEAN,           -- detected booking link / widget
  website_last_modified DATE,            -- if detectable; otherwise null

  -- Scoring + status
  fit_score REAL NOT NULL DEFAULT 0,     -- 0..1
  score_factors JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'new',    -- 'new','outreached','replied','qualified','won','lost','dead'

  -- Audit
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

  CHECK (niche IN ('restaurant','clinic_dental','clinic_medical','clinic_beauty')),
  CHECK (status IN ('new','outreached','replied','qualified','won','lost','dead')),
  CHECK (fit_score >= 0 AND fit_score <= 1)
);

-- Dedupe: one row per Google place
CREATE UNIQUE INDEX IF NOT EXISTS leads_google_place_idx ON leads (google_place_id)
  WHERE google_place_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS leads_status_score_idx ON leads (status, fit_score DESC);
CREATE INDEX IF NOT EXISTS leads_niche_geo_idx ON leads (niche, geo_city);
CREATE INDEX IF NOT EXISTS leads_updated_idx ON leads (updated_at);
