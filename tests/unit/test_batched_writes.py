"""Batched Supabase writes: few round-trips, consistent ids, duplicates merged."""

from __future__ import annotations

from datetime import timedelta

import httpx

from job_scout.models.job import JobSourceRef
from job_scout.services.database import SupabaseJobRepository
from job_scout.services.link_check import LinkStatus, check_job
from job_scout.utils.dates import utcnow
from tests.conftest import canonical_job


class _Query:
    def __init__(self, log, table):
        self.log, self.table = log, table

    def upsert(self, rows, on_conflict=None):
        self.log.append((self.table, rows if isinstance(rows, list) else [rows]))
        return self

    def execute(self):
        return type("R", (), {"data": []})()


class _Client:
    def __init__(self):
        self.log = []

    def table(self, name):
        return _Query(self.log, name)


def _repo() -> SupabaseJobRepository:
    repo = object.__new__(SupabaseJobRepository)
    repo.client = _Client()
    repo._jobs_columns = None
    repo._warned_missing_columns = True
    repo._cache = {}
    repo.jobs_columns = lambda: frozenset()  # filter_job_payload(None-ish) keeps every key
    return repo


def _src(i: int) -> JobSourceRef:
    return JobSourceRef(source_name="greenhouse:x", source_job_id=str(i), source_url=f"https://x/{i}")


def test_batch_mode_groups_writes():
    repo = _repo()
    repo.begin_batch()
    for i in range(450):
        repo.upsert_job(canonical_job(canonical_fingerprint=f"fp{i}"), _src(i))
    repo.flush()
    job_calls = [rows for table, rows in repo.client.log if table == "jobs"]
    source_calls = [rows for table, rows in repo.client.log if table == "job_sources"]
    assert [len(r) for r in job_calls] == [200, 200, 50]
    assert sum(len(r) for r in source_calls) == 450
    ids = {row["canonical_fingerprint"]: row["id"] for rows in job_calls for row in rows}
    for rows in source_calls:
        for row in rows:
            assert row["job_id"] == ids[f"fp{row['source_job_id']}"]
    keys = {frozenset(row) for rows in job_calls for row in rows}
    assert len(keys) == 1  # PostgREST bulk upsert needs identical keys


def test_batch_merges_duplicate_fingerprint_and_keeps_cache():
    repo = _repo()
    repo.begin_batch()
    first = canonical_job(canonical_fingerprint="same")
    repo.upsert_job(first, _src(1))
    cached = repo.get_by_fingerprint("same")
    assert cached is not None and cached.id is not None
    repo.upsert_job(canonical_job(canonical_fingerprint="same"), _src(2))
    repo.flush()
    job_rows = [row for table, rows in repo.client.log if table == "jobs" for row in rows]
    assert len(job_rows) == 1
    assert job_rows[0]["id"] == str(cached.id)  # second write reused the first id
    sources = [row for table, rows in repo.client.log if table == "job_sources" for row in rows]
    assert {row["source_job_id"] for row in sources} == {"1", "2"}


def test_mark_notified_chunks_long_filters():
    calls = []

    class Q:
        def update(self, payload):
            return self

        def in_(self, col, values):
            calls.append(len(values))
            return self

        def execute(self):
            return None

    repo = _repo()
    repo.client = type("C", (), {"table": lambda self, name: Q()})()
    repo.mark_notified([f"{i:064x}" for i in range(256)] + ["0" * 64], utcnow())
    assert calls == [100, 100, 56]  # 256 unique, duplicate dropped, no URL over the limit


def test_flush_without_batch_is_noop():
    repo = _repo()
    assert repo.flush() == 0
    assert repo.client.log == []


def test_no_stale_disables_staleness_rule():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="open")))
    job = canonical_job(canonical_fingerprint="old")
    job.closing_date = None
    job.last_seen_at = utcnow() - timedelta(days=30)
    job.apply_url = job.direct_employer_url = "https://example.com/job/1"
    assert check_job(job, client, stale_days=7).status == LinkStatus.CLOSED
    assert check_job(job, client, stale_days=0).status == LinkStatus.OPEN
