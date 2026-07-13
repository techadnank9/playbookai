-- Playbook AI InsForge schema (PRD §7)
-- Apply with: npx @insforge/cli db query "$(cat docs/schema.sql)"

CREATE TABLE IF NOT EXISTS runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_url    text NOT NULL,
  company_name  text,
  niche         text,
  status        text NOT NULL DEFAULT 'running',
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS findings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id        uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  agent         text NOT NULL,
  platform      text,
  kind          text NOT NULL,
  data          jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS findings_run_id_idx ON findings(run_id);
CREATE INDEX IF NOT EXISTS findings_kind_idx ON findings(kind);
