"""Morning HTML digest. SMTP only; no paid email API."""

from __future__ import annotations

import html
import logging
import smtplib
from dataclasses import dataclass, field
from datetime import date, datetime
from email.message import EmailMessage
from typing import Any

from job_scout.config.settings import Settings, get_settings, load_scoring
from job_scout.models.enums import FitCategory, WorkMode
from job_scout.models.job import CanonicalJobRecord
from job_scout.services.database import JobRepository
from job_scout.utils.dates import utcnow

logger = logging.getLogger(__name__)

MATERIAL_SCORE_DELTA = 8


@dataclass
class DigestSelection:
    jobs: list[CanonicalJobRecord]
    updated_ids: set[str] = field(default_factory=set)
    summary: dict[str, int] = field(default_factory=dict)


def salary_label(job: CanonicalJobRecord) -> str:
    if job.work_mode == WorkMode.REMOTE and not job.salary.published:
        return "Salary: Not published — allowed because role is fully remote"
    if not job.salary.published:
        return "Salary: Not published"
    text = job.salary.raw_text or ""
    monthly = ""
    if job.salary.min_monthly:
        currency = job.salary.currency or ""
        monthly = f" (≈ {currency} {job.salary.min_monthly}/month"
        if job.salary.max_monthly and job.salary.max_monthly != job.salary.min_monthly:
            monthly += f"–{job.salary.max_monthly}"
        monthly += ")"
    return f"Salary: {text}{monthly}".strip()


def job_changed_materially(previous: CanonicalJobRecord | None, current: CanonicalJobRecord) -> bool:
    if previous is None:
        return False
    if (previous.salary.raw_text or "") != (current.salary.raw_text or ""):
        return True
    if previous.closing_date != current.closing_date and current.closing_date:
        return True
    if (previous.direct_employer_url or "") != (current.direct_employer_url or "") and current.direct_employer_url:
        return True
    if previous.fit_score is not None and current.fit_score is not None:
        if current.fit_score - previous.fit_score >= MATERIAL_SCORE_DELTA:
            return True
    return False


def select_digest_jobs(
    jobs: list[CanonicalJobRecord],
    *,
    previous_by_fp: dict[str, CanonicalJobRecord] | None = None,
    min_category: FitCategory = FitCategory.GOOD,
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
    for job in jobs:
        if not job.active or job.rejected:
            continue
        if job.fit_category is None or rank.get(job.fit_category, 0) < min_rank:
            continue
        prev = previous_by_fp.get(job.canonical_fingerprint)
        is_new = job.last_notified_at is None
        changed = job_changed_materially(prev, job) if not is_new else False
        if not is_new and not changed:
            # Prefer new since previous digest; skip exact repeats.
            continue
        if changed:
            updated.add(job.canonical_fingerprint)
        selected.append(job)

    selected.sort(key=lambda item: (-(item.fit_score or 0), item.title))
    summary = {
        "included": len(selected),
        "remote": sum(1 for j in selected if j.work_mode == WorkMode.REMOTE),
        "hybrid": sum(1 for j in selected if j.work_mode == WorkMode.HYBRID),
        "onsite": sum(1 for j in selected if j.work_mode == WorkMode.ONSITE),
        "exceptional": sum(1 for j in selected if j.fit_category == FitCategory.EXCEPTIONAL),
        "strong": sum(1 for j in selected if j.fit_category == FitCategory.STRONG),
        "updated": len(updated),
    }
    return DigestSelection(jobs=selected, updated_ids=updated, summary=summary)


def _card(job: CanonicalJobRecord, updated: bool) -> str:
    apply_url = job.direct_employer_url or job.apply_url or (job.source_urls[0] if job.source_urls else "")
    secondary = ""
    if job.direct_employer_url and job.apply_url and job.apply_url != job.direct_employer_url:
        secondary = f'<p style="margin:4px 0 0;font-size:13px">Secondary source: {html.escape(job.apply_url)}</p>'
    reasons = "".join(f"<li>{html.escape(item)}</li>" for item in job.fit_reasons[:5])
    concerns = "".join(f"<li>{html.escape(item)}</li>" for item in job.concerns[:5])
    badge = "UPDATED · " if updated else ""
    remote = ""
    if job.work_mode == WorkMode.REMOTE:
        remote = f"<p><strong>Remote eligibility:</strong> {html.escape(job.remote_scope.value)}</p>"
    visa = "Unknown" if job.mobility.visa_sponsorship is None else ("Yes" if job.mobility.visa_sponsorship else "No")
    reloc = "Unknown" if job.mobility.relocation_assistance is None else ("Yes" if job.mobility.relocation_assistance else "No")
    work_auth = html.escape(job.mobility.work_authorisation_notes or "Unknown — not inferred")
    first_seen = job.first_seen_at.date().isoformat() if job.first_seen_at else "Unknown"
    posted = job.date_posted.date().isoformat() if job.date_posted else "Unknown"
    closing = job.closing_date.isoformat() if job.closing_date else "Unknown"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;border:1px solid #d8d8d8;border-radius:8px;background:#ffffff">
      <tr><td style="padding:16px;font-family:Arial,sans-serif;color:#222">
        <p style="margin:0 0 6px;font-size:12px;letter-spacing:.04em;color:#555">{badge}{job.fit_category or ''} · {job.fit_score if job.fit_score is not None else '—'}/100</p>
        <h3 style="margin:0 0 8px;font-size:18px;line-height:1.3">{html.escape(job.title)}</h3>
        <p style="margin:0 0 8px"><strong>{html.escape(job.company or 'Unknown company')}</strong><br>
        {html.escape(job.location_text or 'Location unknown')} · {html.escape(job.work_mode.value)}</p>
        {remote}
        <p>{html.escape(salary_label(job))}</p>
        <p>Posted: {posted} · Closing: {closing} · First seen: {first_seen}</p>
        <p>Visa sponsorship: {visa} · Relocation: {reloc}<br>Work-authorisation: {work_auth}</p>
        <p style="margin-bottom:4px"><strong>Why this fits</strong></p>
        <ul style="margin:0 0 8px;padding-left:18px">{reasons}</ul>
        <p style="margin-bottom:4px"><strong>Gaps / concerns</strong></p>
        <ul style="margin:0 0 12px;padding-left:18px">{concerns or '<li>None recorded</li>'}</ul>
        <p style="margin:0"><a href="{html.escape(apply_url)}" style="color:#0b5fff">Apply / view listing</a></p>
        {secondary}
      </td></tr>
    </table>
    """


def render_digest_html(
    selection: DigestSelection,
    *,
    health: dict[str, Any],
    digest_date: date | None = None,
) -> str:
    digest_date = digest_date or utcnow().date()
    sections = []
    for mode, title, colour in (
        (WorkMode.REMOTE, "REMOTE", "#0f6b4c"),
        (WorkMode.HYBRID, "HYBRID", "#8a5a00"),
        (WorkMode.ONSITE, "ON-SITE", "#6b1f3b"),
    ):
        cards = [
            _card(job, job.canonical_fingerprint in selection.updated_ids)
            for job in selection.jobs
            if job.work_mode == mode
        ]
        body = "".join(cards) or '<p style="font-family:Arial,sans-serif;color:#555">No new or updated matches in this section.</p>'
        sections.append(
            f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px">
              <tr><td style="background:{colour};color:#fff;padding:10px 14px;font-family:Arial,sans-serif;font-size:16px;font-weight:bold">{title}</td></tr>
              <tr><td style="padding:12px 0 0">{body}</td></tr>
            </table>
            """
        )
    failed = health.get("failed_sources") or []
    stale = health.get("stale_sources") or []
    last_scrape = health.get("last_successful_scrape") or "unknown"
    summary = selection.summary
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Job Scout</title></head>
<body style="margin:0;padding:0;background:#f3f3f3">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f3f3">
    <tr><td align="center" style="padding:16px">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%">
        <tr><td style="font-family:Arial,sans-serif;padding:8px 0 16px">
          <h1 style="margin:0 0 8px;font-size:22px">Daily Job Scout — {digest_date.strftime('%d %b %Y')}</h1>
          <p style="margin:0;color:#444">New/updated jobs: {summary.get('included', 0)} · Remote {summary.get('remote', 0)} · Hybrid {summary.get('hybrid', 0)} · On-site {summary.get('onsite', 0)} · Exceptional {summary.get('exceptional', 0)} · Strong {summary.get('strong', 0)}</p>
          <p style="margin:8px 0 0;color:#444">Sources checked: {health.get('sources_ok', 0)} ok · {health.get('sources_failed', 0)} failed · New jobs discovered (pipeline): {health.get('new_jobs', 0)}</p>
        </td></tr>
        <tr><td>{''.join(sections)}</td></tr>
        <tr><td style="font-family:Arial,sans-serif;font-size:13px;color:#555;padding:12px 0 24px">
          <p><strong>System health</strong><br>
          Last successful scrape: {html.escape(str(last_scrape))}<br>
          Failed sources: {html.escape(', '.join(failed) or 'none')}<br>
          Stale sources: {html.escape(', '.join(stale) or 'none')}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
"""


def subject_line(selection: DigestSelection, digest_date: date | None = None) -> str:
    digest_date = digest_date or utcnow().date()
    strong = selection.summary.get("exceptional", 0) + selection.summary.get("strong", 0)
    if strong == 0:
        strong = selection.summary.get("included", 0)
    return f"Daily Job Scout — {strong} Strong Matches | {digest_date.strftime('%d %b %Y')}"


def send_smtp(subject: str, html_body: str, settings: Settings) -> None:
    if not settings.has_smtp():
        raise RuntimeError("SMTP settings are incomplete")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = settings.smtp_to
    message.set_content("This digest is HTML. Open it in an HTML-capable client.")
    message.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


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
    jobs = repo.list_digest_candidates(repo.last_digest_at(), min_score)
    previous = {job.canonical_fingerprint: job for job in jobs if job.last_notified_at}
    selection = select_digest_jobs(jobs, previous_by_fp=previous)
    health = {
        "sources_ok": 0,
        "sources_failed": 0,
        "failed_sources": [],
        "stale_sources": [],
        "last_successful_scrape": repo.last_successful_scrape(),
        "new_jobs": selection.summary.get("included", 0),
    }
    for row in repo.list_source_health():
        if row.get("consecutive_failures", 0) > 0 or row.get("status") == "failure":
            health["sources_failed"] += 1
            health["failed_sources"].append(row.get("source"))
        else:
            health["sources_ok"] += 1
        if row.get("consecutive_failures", 0) >= 2:
            health["stale_sources"].append(row.get("source"))
    if extra_health:
        health.update(extra_health)
    html_body = render_digest_html(selection, health=health)
    subject = subject_line(selection)
    result = {
        "subject": subject,
        "html": html_body,
        "jobs": [job.canonical_fingerprint for job in selection.jobs],
        "summary": selection.summary,
        "sent": False,
    }
    if send:
        send_smtp(subject, html_body, settings)
        when = utcnow()
        repo.mark_notified(result["jobs"], when)
        repo.record_digest_run(
            {
                "digest_date": when.date(),
                "generated_at": when,
                "jobs_included": len(result["jobs"]),
                "delivery_status": "sent",
                "recipient": settings.smtp_to,
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
                "recipient": settings.smtp_to or "unset",
            }
        )
    return result
