"""Find saved jobs whose postings have closed, so the dashboard only shows live links.

A job is CLOSED when any of these hold:
  1. its published closing date has passed;
  2. its link answers 404 / 410, or the page says the posting is no longer open;
  3. no scrape has seen it for ``stale_days`` (the board dropped it) - not tombstoned,
     because a source outage looks the same and the job should come back if re-listed.

Anything ambiguous (403, 429, 5xx, timeouts, JavaScript-only pages) is UNKNOWN and kept.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from urllib.parse import urlsplit

import httpx

from job_scout.models.job import CanonicalJobRecord
from job_scout.utils.dates import utcnow

logger = logging.getLogger(__name__)

CLOSED_TEXT = re.compile(
    r"no longer (accepting applications|available|open|active|being accepted)|"
    r"(this|the) (job|position|posting|vacancy|role|requisition) (has )?(been )?(closed|filled|expired|removed)|"
    r"(job|position|posting|vacancy) (is )?(closed|expired|not found|no longer exists)|"
    r"applications (are|have) (now )?closed|page you are looking for (can'?t|cannot|could not) be found|"
    r"job you are looking for (is|was) (no longer|not)",
    re.I,
)
# Hosts whose job pages are client-rendered: a 200 tells us nothing, so only 404/410 count.
SPA_HOSTS = ("myworkdayjobs.com", "ashbyhq.com", "smartrecruiters.com")
UA = "Mozilla/5.0 (compatible; JobScout/1.0; personal job search link check)"


class LinkStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass
class CheckOutcome:
    fingerprint: str
    status: LinkStatus
    reason: str
    tombstone: bool = False


@dataclass
class PruneReport:
    checked: int = 0
    open: int = 0
    unknown: int = 0
    closed: list[CheckOutcome] = field(default_factory=list)
    deleted: int = 0


def job_url(job: CanonicalJobRecord) -> str:
    for candidate in (job.direct_employer_url, job.apply_url, *(job.source_urls or ())):
        if candidate and str(candidate).startswith(("https://", "http://")):
            return str(candidate)
    return ""


def classify_response(url: str, response: httpx.Response) -> tuple[LinkStatus, str]:
    status = response.status_code
    if status in (404, 410):
        return LinkStatus.CLOSED, f"HTTP {status}"
    if status >= 400:
        return LinkStatus.UNKNOWN, f"HTTP {status}"
    final = str(response.url)
    # Greenhouse sends closed postings back to the board with ?error=true.
    if "error=true" in final:
        return LinkStatus.CLOSED, "redirected to board (error=true)"
    original_path = urlsplit(url).path.rstrip("/")
    final_path = urlsplit(final).path.rstrip("/")
    # Lever / Greenhouse job pages that redirect up to the bare board listing.
    if (
        original_path.count("/") >= 2
        and final_path
        and final_path != original_path
        and original_path.startswith(final_path)
        and any(h in urlsplit(final).netloc for h in ("lever.co", "greenhouse.io"))
    ):
        return LinkStatus.CLOSED, "redirected to board root"
    host = urlsplit(final).netloc.lower()
    if any(h in host for h in SPA_HOSTS):
        return LinkStatus.OPEN, "reachable (client-rendered page)"
    ctype = response.headers.get("content-type", "")
    if "html" in ctype or "text" in ctype:
        snippet = response.text[:200_000]
        if CLOSED_TEXT.search(snippet):
            return LinkStatus.CLOSED, "page says posting is closed"
    return LinkStatus.OPEN, f"HTTP {status}"


def check_job(job: CanonicalJobRecord, client: httpx.Client, *, stale_days: int) -> CheckOutcome:
    fp = job.canonical_fingerprint
    now = utcnow()
    if job.closing_date and job.closing_date < now.date():
        return CheckOutcome(fp, LinkStatus.CLOSED, f"closing date {job.closing_date} passed", tombstone=True)
    # A future closing date beats staleness (weekly government circulars roll off the index early).
    if not job.closing_date and job.last_seen_at and job.last_seen_at < now - timedelta(days=stale_days):
        return CheckOutcome(fp, LinkStatus.CLOSED, f"not listed by any source for {stale_days}+ days")
    url = job_url(job)
    if not url:
        return CheckOutcome(fp, LinkStatus.UNKNOWN, "no URL")
    if url.lower().split("?")[0].endswith(".pdf"):
        # Government PDF adverts rarely disappear; rely on closing date / staleness.
        return CheckOutcome(fp, LinkStatus.OPEN, "pdf advert")
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return CheckOutcome(fp, LinkStatus.UNKNOWN, type(exc).__name__)
    status, reason = classify_response(url, response)
    return CheckOutcome(fp, status, reason, tombstone=status == LinkStatus.CLOSED)


def find_closed_jobs(
    jobs: list[CanonicalJobRecord],
    *,
    stale_days: int = 7,
    workers: int = 12,
    timeout: float = 12.0,
) -> PruneReport:
    report = PruneReport()
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
    ) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outcomes = list(pool.map(lambda j: check_job(j, client, stale_days=stale_days), jobs))
    for outcome in outcomes:
        report.checked += 1
        if outcome.status == LinkStatus.CLOSED:
            report.closed.append(outcome)
        elif outcome.status == LinkStatus.OPEN:
            report.open += 1
        else:
            report.unknown += 1
    return report


def prune_closed_jobs(repo, *, dry_run: bool = False, stale_days: int = 7) -> PruneReport:
    jobs = repo.list_active_jobs()
    report = find_closed_jobs(jobs, stale_days=stale_days)
    for outcome in report.closed:
        logger.info("closed: %s (%s)", outcome.fingerprint, outcome.reason)
    if report.closed and not dry_run:
        tombstoned = [o.fingerprint for o in report.closed if o.tombstone]
        untombstoned = [o.fingerprint for o in report.closed if not o.tombstone]
        deleted = 0
        if tombstoned:
            deleted += repo.delete_jobs(tombstoned)
        if untombstoned:
            deleted += repo.delete_jobs(untombstoned, tombstone=False)
        report.deleted = deleted
    logger.info(
        "Link check: %s checked, %s open, %s unknown (kept), %s closed, %s deleted%s",
        report.checked,
        report.open,
        report.unknown,
        len(report.closed),
        report.deleted,
        " (dry run)" if dry_run else "",
    )
    return report
