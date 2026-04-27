-- Phase 6 — chain dedup columns on leads.
-- Many Malaysian clinic chains (Klinik Mediviron, BP Healthcare, Qualitas, etc.)
-- have multiple branches. We want to outreach the chain ONCE, not per branch.
-- Run: cat migrations/006_phase6_chains.sql | ssh ai-primary "sudo docker exec -i postgres psql -U benadmin -d aicore"

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS chain_name TEXT,
  ADD COLUMN IF NOT EXISTS chain_role TEXT NOT NULL DEFAULT 'standalone';

ALTER TABLE leads
  DROP CONSTRAINT IF EXISTS leads_chain_role_check;
ALTER TABLE leads
  ADD CONSTRAINT leads_chain_role_check
  CHECK (chain_role IN ('standalone', 'parent', 'branch'));

CREATE INDEX IF NOT EXISTS leads_chain_idx ON leads (chain_name) WHERE chain_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS leads_chain_role_idx ON leads (chain_role);
