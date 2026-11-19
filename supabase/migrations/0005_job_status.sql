-- Application tracking from the dashboard.
-- The dashboard signs in with a Supabase email link and writes here with the public anon key;
-- row-level security limits every row to the signed-in user. The scraper (service role)
-- reads it so the morning email skips jobs you have already handled.
-- A snapshot of title / company / url is kept so the history survives the job being pruned.

create table if not exists public.job_status (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    canonical_fingerprint text not null,
    status text not null check (status in ('saved', 'applied', 'interviewing', 'offer', 'rejected', 'not_interested')),
    notes text,
    title text,
    company text,
    url text,
    applied_at date,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, canonical_fingerprint)
);

create index if not exists job_status_user_idx on public.job_status (user_id, status);

alter table public.job_status enable row level security;

drop policy if exists "job_status own select" on public.job_status;
drop policy if exists "job_status own insert" on public.job_status;
drop policy if exists "job_status own update" on public.job_status;
drop policy if exists "job_status own delete" on public.job_status;

create policy "job_status own select" on public.job_status
    for select to authenticated using (user_id = auth.uid());
create policy "job_status own insert" on public.job_status
    for insert to authenticated with check (user_id = auth.uid());
create policy "job_status own update" on public.job_status
    for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "job_status own delete" on public.job_status
    for delete to authenticated using (user_id = auth.uid());

-- Only the authenticated role gets table access; anon gets nothing.
revoke all on public.job_status from anon;
grant select, insert, update, delete on public.job_status to authenticated;
