"""Morning HTML digest via Resend (HTTPS API)."""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import httpx

from job_scout.config.settings import Settings, get_settings, load_scoring
from job_scout.models.enums import FitCategory, WorkMode
from job_scout.models.job import CanonicalJobRecord
from job_scout.services.database import JobRepository
from job_scout.services.salary import format_salary_for_display
from job_scout.utils.dates import utcnow
from job_scout.utils.text import strip_html

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"

MATERIAL_SCORE_DELTA = 8

CardStatus = Literal["new", "updated", "returning"]


@dataclass
class DigestSelection:
    jobs: list[CanonicalJobRecord]
    updated_ids: set[str] = field(default_factory=set)
    new_ids: set[str] = field(default_factory=set)
    returning: list[CanonicalJobRecord] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


def salary_label(job: CanonicalJobRecord) -> str:
    if job.work_mode == WorkMode.REMOTE and not job.salary.published:
        return "Salary: Not published — allowed because role is fully remote"
    if not job.salary.published:
        return "Salary: Not published"
    return format_salary_for_display(job.salary)


def job_changed_materially(previous: CanonicalJobRecord | None, current: CanonicalJobRecord) -> bool:
    if previous is None:
        return False
    if (previous.salary.raw_text or "") != (current.salary.raw_text or ""):
        return True
    if previous.closing_date != current.closing_date and current.closing_date:
        return True
    if (previous.direct_employer_url or "") != (current.direct_employer_url or "") and current.direct_employer_url:
        return True
    if (previous.apply_url or "") != (current.apply_url or "") and current.apply_url:
        return True
    if previous.fit_score is not None and current.fit_score is not None:
        if current.fit_score - previous.fit_score >= MATERIAL_SCORE_DELTA:
            return True
    return False


def select_digest_jobs(
    jobs: list[CanonicalJobRecord],
    *,
    previous_by_fp: dict[str, CanonicalJobRecord] | None = None,
    min_category: FitCategory = FitCategory.POSSIBLE,
) -> DigestSelection:
    previous_by_fp = previous_by_fp or {}
    rank = {
        FitCategory.EXCEPTIONAL: 4,
        FitCategory.STRONG: 3,
        FitCategory.GOOD: 2,
        FitCategory.POSSIBLE: 1,
        FitCategory.LOW: 0,
    }
    min_rank = rank[min_category]
    selected: list[CanonicalJobRecord] = []
    updated: set[str] = set()
    new_ids: set[str] = set()
    returning: list[CanonicalJobRecord] = []
    for job in jobs:
        if not job.active or job.rejected:
            continue
        if job.fit_category is None or rank.get(job.fit_category, 0) < min_rank:
            continue
        prev = previous_by_fp.get(job.canonical_fingerprint)
        is_new = job.last_notified_at is None
        changed = bool(job.digest_pending_update)
        if not changed and not is_new:
            changed = job_changed_materially(prev, job)
        if is_new:
            new_ids.add(job.canonical_fingerprint)
            selected.append(job)
            continue
        if changed:
            updated.add(job.canonical_fingerprint)
            selected.append(job)
            continue
        returning.append(job)

    selected.sort(key=lambda item: (-(item.fit_score or 0), item.title))
    returning.sort(key=lambda item: (-(item.fit_score or 0), item.title))
    summary = {
        "included": len(selected),
        "new": len(new_ids),
        "updated": len(updated),
        "returning": len(returning),
        "remote": sum(1 for j in selected if j.work_mode == WorkMode.REMOTE),
        "hybrid": sum(1 for j in selected if j.work_mode == WorkMode.HYBRID),
        "onsite": sum(1 for j in selected if j.work_mode == WorkMode.ONSITE),
        "exceptional": sum(1 for j in selected if j.fit_category == FitCategory.EXCEPTIONAL),
        "strong": sum(1 for j in selected if j.fit_category == FitCategory.STRONG),
        "good": sum(1 for j in selected if j.fit_category == FitCategory.GOOD),
        "possible": sum(1 for j in selected if j.fit_category == FitCategory.POSSIBLE),
    }
    return DigestSelection(
        jobs=selected,
        updated_ids=updated,
        new_ids=new_ids,
        returning=returning,
        summary=summary,
    )


def resolve_apply_url(job: CanonicalJobRecord) -> str:
    for candidate in (job.direct_employer_url, job.apply_url, *(job.source_urls or ())):
        if candidate and str(candidate).strip().startswith("https://"):
            return str(candidate).strip()
        if candidate and str(candidate).strip().startswith("http://"):
            return str(candidate).strip()
    return ""


def apply_url_host(url: str) -> str:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return ""
    parts = host.lower().split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def job_excerpt(job: CanonicalJobRecord, *, max_chars: int = 220) -> str:
    """One short plain-text blurb for the email card — enough context, not a full advert."""
    text = strip_html(job.description or "")
    text = " ".join(text.split())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars + 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "…"


def _region(job: CanonicalJobRecord) -> str:
    cc = (job.country_code or "").upper()
    if cc == "US":
        return "US"
    if cc == "ZA":
        return "ZA"
    return "other"


def _sponsor_stated(job: CanonicalJobRecord) -> bool:
    """Advert says it sponsors, or the employer has engineering green-card (PERM) history."""
    if job.mobility.visa_sponsorship is True:
        return True
    from job_scout.services.scoring import sponsor_history

    return sponsor_history(job) is not None


def _tile(label: str, value: object, *, fg: str, bg: str, border: str) -> str:
    return f"""
    <td width="25%" valign="top" style="padding:5px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {border};border-radius:8px;background:{bg}">
        <tr><td style="padding:10px 12px;font-family:Arial,sans-serif">
          <div style="font-size:26px;line-height:1.1;color:{fg};font-weight:bold">{html.escape(str(value))}</div>
          <div style="font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:{fg};margin-top:4px">{html.escape(label)}</div>
        </td></tr>
      </table>
    </td>
    """


def _top_rows(jobs: list[CanonicalJobRecord], limit: int) -> str:
    rows = []
    for job in jobs[:limit]:
        url = resolve_apply_url(job)
        title = html.escape(job.title)
        if url:
            title = (
                f'<a href="{html.escape(url, quote=True)}" '
                f'style="color:#0f6b4c;text-decoration:none;font-weight:bold">{title}</a>'
            )
        visa = ' &middot; <span style="color:#0f6b4c">visa sponsor</span>' if _sponsor_stated(job) else ""
        score = job.fit_score if job.fit_score is not None else "-"
        where = html.escape(job.location_text or job.work_mode.value)
        rows.append(
            f"""<tr><td style="padding:9px 0;border-top:1px solid #e5e7eb;font-family:Arial,sans-serif;font-size:14px;color:#222">
            <span style="display:inline-block;min-width:34px;font-weight:bold;color:#0f6b4c">{score}</span>{title}<br>
            <span style="font-size:12px;color:#666;padding-left:38px">{html.escape(job.company or "Unknown")} &middot; {where}{visa}</span>
            </td></tr>"""
        )
    return "".join(rows)


def render_digest_html(
    selection: DigestSelection,
    *,
    health: dict[str, Any],
    digest_date: date | None = None,
    dashboard_url: str = "",
    top_n: int = 5,
) -> str:
    """Compact morning summary: counts plus a link to the dashboard. No long job lists."""
    digest_date = digest_date or utcnow().date()
    new_jobs = [j for j in selection.jobs if j.canonical_fingerprint in selection.new_ids]
    s = selection.summary
    strong_new = sum(1 for j in new_jobs if j.fit_category in {FitCategory.EXCEPTIONAL, FitCategory.STRONG})
    us_new = sum(1 for j in new_jobs if _region(j) == "US")
    sponsor_new = sum(1 for j in new_jobs if _sponsor_stated(j))
    open_total = health.get("dashboard_open", s.get("included", 0) + s.get("returning", 0))
    removed = health.get("closed_removed")
    grey = {"fg": "#374151", "bg": "#f9fafb", "border": "#e5e7eb"}
    row1 = "".join(
        [
            _tile("New matches", len(new_jobs), fg="#0f766e", bg="#f0fdfa", border="#99f6e4"),
            _tile("Strong or better", strong_new, fg="#6d28d9", bg="#f5f3ff", border="#c4b5fd"),
            _tile("New in the US", us_new, fg="#1d4ed8", bg="#eff6ff", border="#bfdbfe"),
            _tile("Visa sponsors", sponsor_new, fg="#0f6b4c", bg="#f3faf6", border="#c5ddd2"),
        ]
    )
    row2 = "".join(
        [
            _tile("Remote", sum(1 for j in new_jobs if j.work_mode == WorkMode.REMOTE), **grey),
            _tile("Hybrid", sum(1 for j in new_jobs if j.work_mode == WorkMode.HYBRID), **grey),
            _tile("On-site", sum(1 for j in new_jobs if j.work_mode == WorkMode.ONSITE), **grey),
            _tile("Open on dashboard", open_total, **grey),
        ]
    )
    cta = ""
    if dashboard_url:
        link = html.escape(dashboard_url.rstrip("/") + "/?new=1", quote=True)
        cta = f"""<p style="margin:18px 0 6px;text-align:center">
          <a href="{link}" style="display:inline-block;background:#0f6b4c;color:#ffffff;font-family:Arial,sans-serif;font-size:16px;font-weight:bold;text-decoration:none;padding:14px 26px;border-radius:8px">Open the jobs dashboard &rarr;</a></p>
          <p style="margin:0 0 4px;text-align:center;font-family:Arial,sans-serif;font-size:12px;color:#666">Filter by region, visa sponsorship, fit and work mode. Closed links are removed daily.</p>"""
    if new_jobs:
        more = len(new_jobs) - min(top_n, len(new_jobs))
        more_html = (
            f'<p style="margin:8px 0 0;font-family:Arial,sans-serif;font-size:13px;color:#555">+{more} more on the dashboard.</p>'
            if more > 0
            else ""
        )
        top = f"""<h2 style="margin:22px 0 4px;font-family:Arial,sans-serif;font-size:15px;color:#1a1a1a">Top new matches</h2>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{_top_rows(new_jobs, top_n)}</table>{more_html}"""
    else:
        top = '<p style="margin:18px 0 0;font-family:Arial,sans-serif;color:#555">No new matches since the last summary.</p>'
    apps = health.get("applications") or {}
    pipeline = " · ".join(
        f"{apps[k]} {label}"
        for k, label in (("applied", "applied"), ("interviewing", "interviewing"), ("offer", "offer"), ("saved", "saved"))
        if apps.get(k)
    )
    pipeline_html = (
        f'<p style="margin:0 0 12px;font-size:13px;color:#0f6b4c"><strong>Your applications:</strong> {html.escape(pipeline)}</p>'
        if pipeline
        else ""
    )
    failed = [str(item) for item in (health.get("failed_sources") or []) if item]
    health_bits = [f"Sources {health.get('sources_ok', 0)} ok / {health.get('sources_failed', 0)} failing"]
    if removed is not None:
        health_bits.append(f"{removed} closed jobs removed")
    if failed:
        health_bits.append("failing: " + ", ".join(failed[:6]))
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Scout summary</title></head>
<body style="margin:0;padding:0;background:#f3f3f3">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f3f3">
    <tr><td align="center" style="padding:16px">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px">
        <tr><td style="padding:20px 20px 8px;font-family:Arial,sans-serif">
          <h1 style="margin:0;font-size:20px;color:#1a1a1a">Job Scout &middot; {digest_date.strftime('%d %b %Y')}</h1>
          <p style="margin:4px 0 12px;font-size:13px;color:#555">{len(new_jobs)} new matching jobs since the last summary.</p>
          {pipeline_html}
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{row1}</tr><tr>{row2}</tr></table>
          {cta}
          {top}
        </td></tr>
        <tr><td style="padding:14px 20px 18px;font-family:Arial,sans-serif;font-size:12px;color:#777">{html.escape(" · ".join(health_bits))}</td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


def subject_line(selection: DigestSelection, digest_date: date | None = None) -> str:
    digest_date = digest_date or utcnow().date()
    new = selection.summary.get("new", 0)
    strong_new = sum(
        1
        for j in selection.jobs
        if j.canonical_fingerprint in selection.new_ids
        and j.fit_category in {FitCategory.EXCEPTIONAL, FitCategory.STRONG}
    )
    date_s = digest_date.strftime("%d %b")
    if strong_new:
        return f"Job Scout: {new} new jobs ({strong_new} strong) | {date_s}"
    return f"Job Scout: {new} new jobs | {date_s}"


def send_resend(subject: str, html_body: str, settings: Settings) -> dict[str, Any]:
    if not settings.has_resend():
        raise RuntimeError(
            "Resend settings are incomplete. Set RESEND_API_KEY, RESEND_FROM and DIGEST_TO."
        )
    payload = {
        "from": settings.resend_from,
        "to": [settings.digest_to],
        "subject": subject,
        "html": html_body,
        "text": f"{subject}\n\nOpen the dashboard: {settings.dashboard_url}",
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(RESEND_API_URL, headers=headers, json=payload)
        if response.status_code >= 400:
            raise RuntimeError(f"Resend API error {response.status_code}: {response.text}")
        data = response.json()
    logger.info("Resend accepted digest email id=%s", data.get("id"))
    return data if isinstance(data, dict) else {"raw": data}


def build_and_maybe_send(
    repo: JobRepository,
    *,
    settings: Settings | None = None,
    send: bool = False,
    extra_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    scoring = load_scoring(settings)
    min_score = int(scoring.get("low_score_cutoff", 60))
    min_name = str(scoring.get("digest_minimum_category") or "Possible")
    try:
        min_category = FitCategory(min_name)
    except ValueError:
        min_category = FitCategory.POSSIBLE
    jobs = repo.list_digest_candidates(repo.last_digest_at(), min_score)
    # Jobs you have already tracked on the dashboard (applied, rejected, not interested...)
    # are not "new" to you; leave them out and summarise your pipeline instead.
    statuses = repo.list_job_statuses() if hasattr(repo, "list_job_statuses") else {}
    if statuses:
        jobs = [job for job in jobs if job.canonical_fingerprint not in statuses]
    previous = {job.canonical_fingerprint: job for job in jobs if job.last_notified_at}
    selection = select_digest_jobs(jobs, previous_by_fp=previous, min_category=min_category)
    health = {
        "sources_ok": 0,
        "sources_failed": 0,
        "failed_sources": [],
        "stale_sources": [],
        "last_successful_scrape": repo.last_successful_scrape(),
        "new_jobs": selection.summary.get("new", 0),
        "jobs_found": 0,
        "jobs_discarded": 0,
    }
    try:
        totals = repo.recent_scrape_totals()
        health["jobs_found"] = totals.get("jobs_found", 0)
        health["jobs_discarded"] = totals.get("jobs_discarded", 0)
        if totals.get("jobs_new") is not None:
            health["pipeline_new"] = totals["jobs_new"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load scrape totals for digest header: %s", exc)
    from job_scout.adapters.registry import inactive_source_names

    try:
        inactive = inactive_source_names()
    except Exception:  # noqa: BLE001
        inactive = set()
    for row in repo.list_source_health():
        if row.get("source") in inactive:
            continue
        if row.get("consecutive_failures", 0) > 0 or row.get("status") == "failure":
            health["sources_failed"] += 1
            health["failed_sources"].append(row.get("source"))
        else:
            health["sources_ok"] += 1
        if row.get("consecutive_failures", 0) >= 2:
            health["stale_sources"].append(row.get("source"))
    if hasattr(repo, "list_active_jobs"):
        try:
            health["dashboard_open"] = sum(
                1 for job in repo.list_active_jobs() if job.fit_score is not None and job.fit_score >= min_score
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not count open dashboard jobs: %s", exc)
    if statuses:
        counts: dict[str, int] = {}
        for status in statuses.values():
            counts[status] = counts.get(status, 0) + 1
        health["applications"] = counts
    if extra_health:
        health.update(extra_health)
    html_body = render_digest_html(selection, health=health, dashboard_url=settings.dashboard_url)
    subject = subject_line(selection)
    result = {
        "subject": subject,
        "html": html_body,
        "jobs": [job.canonical_fingerprint for job in selection.jobs],
        "returning_jobs": [job.canonical_fingerprint for job in selection.returning],
        "summary": selection.summary,
        "sent": False,
    }
    if send:
        send_resend(subject, html_body, settings)
        when = utcnow()
        # Mark both featured and still-open listings that appeared in this email.
        repo.mark_notified([*result["jobs"], *result["returning_jobs"]], when)
        repo.record_digest_run(
            {
                "digest_date": when.date(),
                "generated_at": when,
                "jobs_included": len(result["jobs"]),
                "delivery_status": "sent",
                "recipient": settings.digest_to,
            }
        )
        result["sent"] = True
    else:
        repo.record_digest_run(
            {
                "digest_date": utcnow().date(),
                "generated_at": utcnow(),
                "jobs_included": len(result["jobs"]),
                "delivery_status": "dry_run",
                "recipient": settings.digest_to or "unset",
            }
        )
    return result
