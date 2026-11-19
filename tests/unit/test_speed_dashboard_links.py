"""Fetch budget, link checker, visa detection, dashboard build and Workday parsing."""

from __future__ import annotations

import time
from datetime import timedelta

import httpx
import pytest

from job_scout.adapters.base import SourceAdapter
from job_scout.models.enums import FitCategory, SourceType, WorkMode
from job_scout.models.job import RawJobRecord
from job_scout.services.database import InMemoryJobRepository
from job_scout.services.link_check import LinkStatus, check_job, classify_response, find_closed_jobs
from job_scout.services.mobility import extract_mobility
from job_scout.utils.dates import utcnow
from tests.conftest import canonical_job


def _raw(**kw) -> RawJobRecord:
    base = dict(source_name="t", source_type=SourceType.API, source_job_id="1", source_url="https://x/1", title="Mechanical Engineer")
    base.update(kw)
    return RawJobRecord(**base)


# --- fetch phase -------------------------------------------------------------------------


class _Slow(SourceAdapter):
    source_name = "slow"
    source_type = SourceType.API

    def fetch_jobs(self):
        for i in range(1000):
            time.sleep(0.01)
            yield _raw(source_job_id=str(i))


class _Boom(SourceAdapter):
    source_name = "boom"
    source_type = SourceType.API

    def fetch_jobs(self):
        raise RuntimeError("down")
        yield  # pragma: no cover


def test_prefetch_respects_budget_and_isolates_failures():
    from job_scout.pipelines.fetching import prefetch_sources

    t0 = time.perf_counter()
    results = prefetch_sources(
        [_Slow({"name": "slow"}), _Boom({"name": "boom"}), _Slow({"name": "slow"})],
        budget_seconds=0.3,
        workers=4,
    )
    assert time.perf_counter() - t0 < 3
    assert set(results) == {"slow", "boom"}  # duplicates fetched once
    assert results["slow"].budget_hit and 0 < len(results["slow"].jobs) < 1000
    assert isinstance(results["boom"].error, RuntimeError)


def test_http_client_fails_fast_after_deadline():
    from job_scout.adapters.http import FETCH_DEADLINE, HttpClient, SourceBudgetExceeded

    client = HttpClient(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))))
    token = FETCH_DEADLINE.set(time.monotonic() - 1)
    try:
        with pytest.raises(SourceBudgetExceeded):
            client.request("GET", "https://example.com", delay=0)
    finally:
        FETCH_DEADLINE.reset(token)


def test_http_client_does_not_retry_403():
    from job_scout.adapters.http import HttpClient

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403)

    client = HttpClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(httpx.HTTPStatusError):
        client.request("GET", "https://example.com", delay=0)
    assert len(calls) == 1


# --- link checker ------------------------------------------------------------------------


def _resp(url: str, status: int = 200, text: str = "<html>ok</html>", final: str | None = None) -> httpx.Response:
    return httpx.Response(
        status,
        text=text,
        headers={"content-type": "text/html"},
        request=httpx.Request("GET", final or url),
    )


@pytest.mark.parametrize(
    "status,text,final,expected",
    [
        (404, "", None, LinkStatus.CLOSED),
        (410, "", None, LinkStatus.CLOSED),
        (403, "", None, LinkStatus.UNKNOWN),
        (503, "", None, LinkStatus.UNKNOWN),
        (200, "<p>Apply now for this role</p>", None, LinkStatus.OPEN),
        (200, "<h1>This job is no longer accepting applications</h1>", None, LinkStatus.CLOSED),
        (200, "<p>The position has been filled.</p>", None, LinkStatus.CLOSED),
        (200, "board", "https://boards.greenhouse.io/acme?error=true", LinkStatus.CLOSED),
        (200, "board", "https://jobs.lever.co/acme", LinkStatus.CLOSED),
    ],
)
def test_classify_response(status, text, final, expected):
    url = "https://jobs.lever.co/acme/1234-abcd" if final and "lever" in final else "https://example.com/jobs/1"
    status_out, _ = classify_response(url, _resp(url, status, text, final))
    assert status_out == expected


def test_workday_spa_200_counts_as_open_even_with_generic_text():
    url = "https://xylem.wd5.myworkdayjobs.com/en-US/xylem-careers/job/X_1"
    status, _ = classify_response(url, _resp(url, 200, "page you are looking for cannot be found"))
    assert status == LinkStatus.OPEN


def test_closing_date_and_staleness_rules():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="open")))
    past = canonical_job(canonical_fingerprint="past")
    past.closing_date = (utcnow() - timedelta(days=1)).date()
    assert check_job(past, client, stale_days=7).status == LinkStatus.CLOSED
    assert check_job(past, client, stale_days=7).tombstone is True

    stale = canonical_job(canonical_fingerprint="stale")
    stale.closing_date = None
    stale.last_seen_at = utcnow() - timedelta(days=10)
    outcome = check_job(stale, client, stale_days=7)
    assert outcome.status == LinkStatus.CLOSED and outcome.tombstone is False

    # Future closing date overrides staleness (weekly government circulars).
    circular = canonical_job(canonical_fingerprint="circ")
    circular.closing_date = (utcnow() + timedelta(days=5)).date()
    circular.last_seen_at = utcnow() - timedelta(days=10)
    circular.apply_url = "https://example.com/advert.pdf"
    circular.direct_employer_url = None
    circular.source_urls = []
    assert check_job(circular, client, stale_days=7).status == LinkStatus.OPEN


def test_prune_deletes_and_tombstones_closed_jobs(monkeypatch):
    from job_scout.services import link_check

    repo = InMemoryJobRepository()
    for fp in ("open", "gone"):
        job = canonical_job(canonical_fingerprint=fp)
        job.closing_date = None
        job.apply_url = job.direct_employer_url = f"https://example.com/{fp}"
        job.fit_score = 80
        job.last_seen_at = utcnow()
        repo.jobs[fp] = job

    def fake_find(jobs, stale_days):
        report = link_check.PruneReport()
        report.checked = len(jobs)
        report.closed = [link_check.CheckOutcome("gone", LinkStatus.CLOSED, "HTTP 404", tombstone=True)]
        return report

    monkeypatch.setattr(link_check, "find_closed_jobs", fake_find)
    report = link_check.prune_closed_jobs(repo)
    assert report.deleted == 1
    assert set(repo.jobs) == {"open"}
    assert repo.is_closed("gone")


# --- visa detection ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,visa,citizen",
    [
        ("We offer H-1B sponsorship for qualified candidates.", True, None),
        ("Visa sponsorship is available, including green card (PERM) sponsorship.", True, None),
        ("This role is eligible for EB-2 green card sponsorship.", True, None),
        ("We are unable to sponsor visas for this position.", False, None),
        ("Candidates must be authorized to work in the US without sponsorship.", False, None),
        ("This position requires access to ITAR-controlled data; applicants must be U.S. persons.", None, True),
        ("Great benefits and a collaborative team.", None, None),
    ],
)
def test_visa_detection(text, visa, citizen):
    flags = extract_mobility("Mechanical Engineer", text, _raw())
    assert flags.visa_sponsorship is visa
    assert flags.citizenship_required is citizen


def test_green_card_note_recorded():
    flags = extract_mobility("Engineer", "Visa sponsorship is available and we sponsor green cards.", _raw())
    assert "green card" in (flags.work_authorisation_notes or "")


# --- dashboard ---------------------------------------------------------------------------


def test_dashboard_writes_filtered_sorted_jobs(tmp_path):
    from job_scout.services.dashboard import build_dashboard

    good = canonical_job(title="Water Engineer <script>", canonical_fingerprint="a")
    good.fit_score, good.fit_category, good.country_code = 88, FitCategory.STRONG, "US"
    good.mobility.visa_sponsorship = True
    good.first_seen_at = utcnow()
    low = canonical_job(title="Low Fit", canonical_fingerprint="b")
    low.fit_score, low.fit_category = 30, FitCategory.LOW
    stats = build_dashboard([low, good], tmp_path, min_score=60)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert stats == {"open": 1, "new_7d": 1, "us": 1, "sponsor": 1}
    assert "Water Engineer" in html and "Low Fit" not in html
    # The title's "<script>" must not appear raw inside the inline JSON block.
    assert html.count("<script>") == 1
    assert "</script>\n</body>" in html  # inline JSON did not break the page
    assert (tmp_path / ".nojekyll").exists()


# --- Workday ----------------------------------------------------------------------------


def test_workday_parse_job():
    from job_scout.adapters.ats.workday import WorkdayAdapter

    raw = WorkdayAdapter({}).parse_job(
        {
            "title": "Senior Mechanical Engineer",
            "jobDescription": "<p>Design pumps. We offer H-1B sponsorship.</p>",
            "location": "Houston, TX",
            "country": {"descriptor": "United States of America"},
            "remoteType": "Hybrid",
            "jobReqId": "R123",
            "startDate": "2026-11-10",
            "_company": "Xylem",
            "_tenant": "xylem",
            "_public_url": "https://xylem.wd5.myworkdayjobs.com/en-US/xylem-careers/job/R123",
        }
    )
    assert raw.source_name == "workday:xylem"
    assert raw.work_mode_hint == "hybrid"
    assert "United States" in (raw.location_text or "")
    assert raw.apply_url.endswith("/R123")
    assert "Design pumps" in (raw.description_text or "")
