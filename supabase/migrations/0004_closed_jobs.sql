-- Tombstones for jobs the link checker deleted because the posting closed.
-- Scrapes skip these fingerprints so a stale aggregator listing cannot resurrect a dead job.
-- Apply in the Supabase SQL editor. The code keeps working (without tombstones) until you do.

create table if not exists public.closed_jobs (
    canonical_fingerprint text primary key,
    closed_at timestamptz not null default now()
);

alter table public.closed_jobs enable row level security;

-- Housekeeping: tombstones older than 120 days are no longer useful.
-- delete from public.closed_jobs where closed_at < now() - interval '120 days';
