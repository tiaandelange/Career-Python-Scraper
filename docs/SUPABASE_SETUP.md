# Supabase setup

The GitHub Action and local CLI write with the **service role** key. That key must never appear in client-side code, README examples with real values, or git history.

## Steps

1. Create a free Supabase project.
2. Open **SQL Editor** and run `supabase/migrations/0001_init.sql`.
3. Confirm tables: `jobs`, `job_sources`, `scrape_runs`, `source_health`, `digest_runs`, `fx_rates`.
4. Copy **Project URL** and **service_role** key from Project Settings → API.
5. Put them in `.env` locally and in GitHub Actions secrets.
6. Leave Row Level Security enabled. There are no anon policies, so the public anon key cannot read jobs.

The Python repository layer (`job_scout.services.database`) is the only writer. Source adapters never issue SQL.

Tests use `InMemoryJobRepository` and do not touch production.
