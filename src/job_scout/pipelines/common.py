"""Shared pipeline: fetch → parse → normalise → filter → dedupe → score → persist."""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.config.settings import load_profile, load_salary_policy, load_scoring
from job_scout.models.enums import PipelineName, WorkMode
from job_scout.models.job import CanonicalJobRecord, PipelineStats, RawJobRecord
from job_scout.services.ageing import apply_ageing
from job_scout.services.database import JobRepository
from job_scout.services.deduplication import DuplicateIndex, source_ref_from, to_canonical
from job_scout.services.eligibility import apply_hard_filters
from job_scout.services.fx import FxService
from job_scout.services.normalisation import normalise_job
from job_scout.services.scoring import score_job
from job_scout.services.source_health import record_failure, record_parser_anomaly, record_success
from job_scout.utils.dates import utcnow
from job_scout.utils.text import normalise_key

logger = logging.getLogger(__name__)


def is_family_relevant(title: str, description: str, profile: dict[str, Any]) -> bool:
    blob = normalise_key(f"{title} {description[:2500]}")
    for family in (profile.get("job_families") or {}).values():
        for title_opt in family.get("titles") or []:
            if normalise_key(title_opt) in blob:
                return True
        for keyword in family.get("keywords") or []:
            if normalise_key(keyword) in blob:
                return True
    return False


def attach_usd(job: CanonicalJobRecord, fx: FxService | None) -> None:
    monthly = job.salary.min_monthly or job.salary.max_monthly
    if monthly is None or not job.salary.currency or fx is None:
        return
    try:
        usd, stale = fx.convert(monthly, job.salary.currency, "USD")
        job.salary.usd_monthly = usd
        job.salary.fx_stale = stale
    except Exception as exc:  # noqa: BLE001
        logger.warning("FX convert failed: %s", exc)
        job.flags.append("fx_unavailable")


def _critical_fields(raw: RawJobRecord) -> list[str]:
    missing = []
    if not raw.title:
        missing.append("title")
    if not raw.company:
        missing.append("company")
    if not (raw.apply_url or raw.source_url):
        missing.append("application_url")
    return missing


def run_pipeline(
    *,
    pipeline: PipelineName,
    adapters: Iterable[SourceAdapter],
    repo: JobRepository,
    fx: FxService | None = None,
    expected_work_mode: WorkMode | None = None,
) -> PipelineStats:
    profile = load_profile()
    policy = load_salary_policy()
    scoring = load_scoring()
    stats = PipelineStats(pipeline=pipeline.value)
    index = DuplicateIndex()
    started = utcnow()
    t0 = time.perf_counter()

    for adapter in adapters:
        stats.sources_checked += 1
        source = adapter.source_name
        seen = 0
        parse_errors = 0
        try:
            jobs = list(adapter.fetch_jobs())
        except Exception as exc:  # noqa: BLE001
            stats.sources_failed += 1
            stats.failures.append(f"{source}: {exc}")
            record_failure(repo, source, str(exc), extra={"response_status": None})
            continue

        missing_critical: list[str] = []
        for raw in jobs:
            seen += 1
            stats.raw_jobs += 1
            missing = _critical_fields(raw)
            if missing:
                parse_errors += 1
                missing_critical.extend(missing)
                continue
            try:
                normalised = normalise_job(raw)
            except Exception as exc:  # noqa: BLE001
                parse_errors += 1
                logger.warning("Parse/normalise failed for %s: %s", source, exc)
                continue
            if expected_work_mode and normalised.work_mode not in {expected_work_mode, WorkMode.UNKNOWN}:
                if expected_work_mode == WorkMode.REMOTE and normalised.work_mode != WorkMode.REMOTE:
                    continue
                if expected_work_mode != WorkMode.REMOTE and normalised.work_mode != expected_work_mode:
                    continue
            if expected_work_mode == WorkMode.REMOTE and normalised.work_mode == WorkMode.UNKNOWN:
                normalised.work_mode = WorkMode.REMOTE
            if not is_family_relevant(normalised.title, normalised.description, profile):
                continue
            stats.relevant += 1
            decision = apply_hard_filters(normalised, profile=profile, policy=policy, fx=fx)
            normalised.flags.extend(decision.flags)
            canonical = to_canonical(normalised)
            attach_usd(canonical, fx)
            if not decision.accepted:
                canonical.rejected = True
                canonical.rejection_reasons = decision.reasons
                stats.rejected += 1
                if any("salary" in reason for reason in decision.reasons):
                    stats.rejected_salary += 1
                if any("remote_restricted" in reason or "country_not_in_target" in reason for reason in decision.reasons):
                    stats.rejected_geo += 1
                continue
            canonical = score_job(canonical, profile=profile, scoring=scoring)
            before = repo.get_by_fingerprint(canonical.canonical_fingerprint)
            merged = index.add(canonical, source_ref_from(normalised))
            if merged is not canonical and merged.canonical_fingerprint != canonical.canonical_fingerprint:
                stats.duplicates_merged += 1
            stored = repo.upsert_job(merged, source_ref_from(normalised))
            if before is None:
                stats.new += 1
            else:
                stats.updated += 1
            _ = stored

        stats.parse_errors += parse_errors
        if seen == 0:
            employers = adapter.config.get("employers")
            if isinstance(employers, list) and len(employers) == 0:
                record_success(repo, source, 0, extra={"note": "no_employers_configured"})
            else:
                record_failure(repo, source, "zero_jobs_returned")
        else:
            record_success(repo, source, seen, extra={"parse_errors": parse_errors})
            if missing_critical:
                record_parser_anomaly(repo, source, sorted(set(missing_critical)))

    apply_ageing(repo)
    duration = time.perf_counter() - t0
    repo.record_scrape_run(
        {
            "started_at": started,
            "ended_at": utcnow(),
            "pipeline": pipeline.value,
            "source": "all",
            "status": "partial" if stats.sources_failed else "success",
            "jobs_seen": stats.raw_jobs,
            "jobs_new": stats.new,
            "jobs_updated": stats.updated,
            "jobs_rejected": stats.rejected,
            "error_information": "; ".join(stats.failures) or None,
            "duration_seconds": round(duration, 2),
        }
    )
    logger.info(
        "%s: %s sources checked, %s raw, %s relevant, %s new, %s failures",
        pipeline.value,
        stats.sources_checked,
        stats.raw_jobs,
        stats.relevant,
        stats.new,
        stats.sources_failed,
    )
    return stats
