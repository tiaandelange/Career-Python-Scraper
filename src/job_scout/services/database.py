"""Persistence layer. Adapters never execute SQL."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import uuid4

from job_scout.config.settings import Settings, get_settings
from job_scout.models.enums import FitCategory, WorkMode
from job_scout.models.job import CanonicalJobRecord, JobSourceRef, MobilityFlags, SalarySnapshot, ScoreBreakdown
from job_scout.utils.dates import utcnow

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


class JobRepository(Protocol):
    def upsert_job(self, job: CanonicalJobRecord, source: JobSourceRef) -> CanonicalJobRecord: ...
    def get_by_fingerprint(self, fingerprint: str) -> CanonicalJobRecord | None: ...
    def list_digest_candidates(self, since: datetime | None, min_score: int) -> list[CanonicalJobRecord]: ...
    def mark_notified(self, fingerprints: list[str], when: datetime) -> None: ...
    def record_scrape_run(self, payload: dict[str, Any]) -> None: ...
    def record_source_health(self, payload: dict[str, Any]) -> None: ...
    def record_digest_run(self, payload: dict[str, Any]) -> None: ...
    def save_fx_rate(self, base: str, quote: str, on: date, rate: Decimal, stale: bool = False) -> None: ...
    def get_fx_rate(self, base: str, quote: str, on: date) -> tuple[Decimal, bool] | None: ...
    def latest_fx_rate(self, base: str, quote: str) -> tuple[Decimal, date, bool] | None: ...
    def list_source_health(self) -> list[dict[str, Any]]: ...
    def last_successful_scrape(self) -> datetime | None: ...
    def last_digest_at(self) -> datetime | None: ...
    def ping(self) -> dict[str, Any]: ...
    def expire_jobs(self, missing_streak: int = 3) -> int: ...


class InMemoryJobRepository:
    """Used by tests. Never talks to production Supabase."""

    def __init__(self) -> None:
        self.jobs: dict[str, CanonicalJobRecord] = {}
        self.sources: dict[str, list[JobSourceRef]] = {}
        self.scrape_runs: list[dict[str, Any]] = []
        self.source_health: dict[str, dict[str, Any]] = {}
        self.digest_runs: list[dict[str, Any]] = []
        self.fx_rates: dict[tuple[str, str, date], tuple[Decimal, bool]] = {}
        self.missing_counts: dict[str, int] = {}

    def upsert_job(self, job: CanonicalJobRecord, source: JobSourceRef) -> CanonicalJobRecord:
        existing = self.jobs.get(job.canonical_fingerprint)
        now = utcnow()
        if existing:
            job.id = existing.id
            job.first_seen_at = existing.first_seen_at
            job.last_notified_at = existing.last_notified_at
            job.source_urls = list(dict.fromkeys([*existing.source_urls, *job.source_urls]))
        else:
            job.id = job.id or uuid4()
            job.first_seen_at = now
        job.last_seen_at = now
        self.jobs[job.canonical_fingerprint] = job
        self.sources.setdefault(job.canonical_fingerprint, [])
        if not any(s.source_url == source.source_url for s in self.sources[job.canonical_fingerprint]):
            self.sources[job.canonical_fingerprint].append(source)
        self.missing_counts[job.canonical_fingerprint] = 0
        return job

    def get_by_fingerprint(self, fingerprint: str) -> CanonicalJobRecord | None:
        return self.jobs.get(fingerprint)

    def list_digest_candidates(self, since: datetime | None, min_score: int) -> list[CanonicalJobRecord]:
        out = []
        for job in self.jobs.values():
            if not job.active or job.rejected:
                continue
            if job.fit_score is None or job.fit_score < min_score:
                continue
            out.append(job)
        return out

    def mark_notified(self, fingerprints: list[str], when: datetime) -> None:
        for fp in fingerprints:
            job = self.jobs.get(fp)
            if job:
                job.last_notified_at = when

    def record_scrape_run(self, payload: dict[str, Any]) -> None:
        self.scrape_runs.append(payload)

    def record_source_health(self, payload: dict[str, Any]) -> None:
        self.source_health[payload["source"]] = payload

    def record_digest_run(self, payload: dict[str, Any]) -> None:
        self.digest_runs.append(payload)

    def save_fx_rate(self, base: str, quote: str, on: date, rate: Decimal, stale: bool = False) -> None:
        self.fx_rates[(base.upper(), quote.upper(), on)] = (rate, stale)

    def get_fx_rate(self, base: str, quote: str, on: date) -> tuple[Decimal, bool] | None:
        return self.fx_rates.get((base.upper(), quote.upper(), on))

    def latest_fx_rate(self, base: str, quote: str) -> tuple[Decimal, date, bool] | None:
        matches = [
            (on, rate, stale)
            for (b, q, on), (rate, stale) in self.fx_rates.items()
            if b == base.upper() and q == quote.upper()
        ]
        if not matches:
            return None
        on, rate, stale = max(matches, key=lambda item: item[0])
        return rate, on, stale

    def list_source_health(self) -> list[dict[str, Any]]:
        return list(self.source_health.values())

    def last_successful_scrape(self) -> datetime | None:
        times = [
            row.get("ended_at")
            for row in self.scrape_runs
            if row.get("status") in {"success", "partial"}
        ]
        times = [t for t in times if t]
        return max(times) if times else None

    def last_digest_at(self) -> datetime | None:
        sent = [row.get("generated_at") for row in self.digest_runs if row.get("status") == "sent"]
        sent = [t for t in sent if t]
        return max(sent) if sent else None

    def ping(self) -> dict[str, Any]:
        return {"ok": True, "backend": "memory", "jobs": len(self.jobs)}

    def expire_jobs(self, missing_streak: int = 3) -> int:
        now = utcnow().date()
        expired = 0
        for job in self.jobs.values():
            if job.closing_date and job.closing_date < now:
                job.active = False
                expired += 1
        return expired


class SupabaseFxStore:
    def __init__(self, repo: JobRepository) -> None:
        self.repo = repo

    def get_rate(self, base: str, quote: str, on: date) -> tuple[Decimal, bool] | None:
        return self.repo.get_fx_rate(base, quote, on)

    def latest_rate(self, base: str, quote: str) -> tuple[Decimal, date, bool] | None:
        return self.repo.latest_fx_rate(base, quote)

    def save_rate(self, base: str, quote: str, on: date, rate: Decimal, stale: bool = False) -> None:
        self.repo.save_fx_rate(base, quote, on, rate, stale)


class SupabaseJobRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.has_supabase():
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
        from supabase import create_client

        self.client = create_client(self.settings.supabase_url, self.settings.supabase_service_role_key)

    def upsert_job(self, job: CanonicalJobRecord, source: JobSourceRef) -> CanonicalJobRecord:
        now = utcnow()
        existing = self.get_by_fingerprint(job.canonical_fingerprint)
        payload = _job_row(job, existing, now)
        self.client.table("jobs").upsert(payload, on_conflict="canonical_fingerprint").execute()
        stored = self.get_by_fingerprint(job.canonical_fingerprint)
        if stored and stored.id:
            self.client.table("job_sources").upsert(
                {
                    "job_id": str(stored.id),
                    "source_name": source.source_name,
                    "source_job_id": source.source_job_id,
                    "source_url": source.source_url,
                    "direct_employer_url": source.direct_employer_url,
                    "last_seen_at": now.isoformat(),
                },
                on_conflict="source_name,source_job_id",
            ).execute()
        return stored or job

    def get_by_fingerprint(self, fingerprint: str) -> CanonicalJobRecord | None:
        result = self.client.table("jobs").select("*").eq("canonical_fingerprint", fingerprint).limit(1).execute()
        rows = result.data or []
        if not rows:
            return None
        return _row_to_job(rows[0])

    def list_digest_candidates(self, since: datetime | None, min_score: int) -> list[CanonicalJobRecord]:
        query = (
            self.client.table("jobs")
            .select("*")
            .eq("active", True)
            .gte("fit_score", min_score)
        )
        result = query.execute()
        return [_row_to_job(row) for row in (result.data or [])]

    def mark_notified(self, fingerprints: list[str], when: datetime) -> None:
        if not fingerprints:
            return
        self.client.table("jobs").update({"last_notified_at": when.isoformat()}).in_(
            "canonical_fingerprint", fingerprints
        ).execute()

    def record_scrape_run(self, payload: dict[str, Any]) -> None:
        allowed = {
            "started_at",
            "ended_at",
            "pipeline",
            "source",
            "status",
            "jobs_seen",
            "jobs_new",
            "jobs_updated",
            "jobs_rejected",
            "error_information",
            "duration_seconds",
        }
        row = _json_row({key: value for key, value in payload.items() if key in allowed})
        self.client.table("scrape_runs").insert(row).execute()

    def record_source_health(self, payload: dict[str, Any]) -> None:
        allowed = {
            "source",
            "last_success",
            "last_failure",
            "consecutive_failures",
            "response_status",
            "error_summary",
            "status",
            "jobs_seen",
            "updated_at",
        }
        filtered = {key: value for key, value in payload.items() if key in allowed}
        if "updated_at" not in filtered:
            filtered["updated_at"] = utcnow()
        row = _json_row(filtered)
        self.client.table("source_health").upsert(row, on_conflict="source").execute()

    def record_digest_run(self, payload: dict[str, Any]) -> None:
        self.client.table("digest_runs").insert(_json_row(payload)).execute()

    def save_fx_rate(self, base: str, quote: str, on: date, rate: Decimal, stale: bool = False) -> None:
        self.client.table("fx_rates").upsert(
            {
                "base_currency": base.upper(),
                "quote_currency": quote.upper(),
                "rate_date": on.isoformat(),
                "rate": float(rate),
                "stale": stale,
                "fetched_at": utcnow().isoformat(),
            },
            on_conflict="base_currency,quote_currency,rate_date",
        ).execute()

    def get_fx_rate(self, base: str, quote: str, on: date) -> tuple[Decimal, bool] | None:
        result = (
            self.client.table("fx_rates")
            .select("*")
            .eq("base_currency", base.upper())
            .eq("quote_currency", quote.upper())
            .eq("rate_date", on.isoformat())
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        return Decimal(str(rows[0]["rate"])), bool(rows[0].get("stale"))

    def latest_fx_rate(self, base: str, quote: str) -> tuple[Decimal, date, bool] | None:
        result = (
            self.client.table("fx_rates")
            .select("*")
            .eq("base_currency", base.upper())
            .eq("quote_currency", quote.upper())
            .order("rate_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        return Decimal(str(row["rate"])), date.fromisoformat(row["rate_date"]), bool(row.get("stale"))

    def list_source_health(self) -> list[dict[str, Any]]:
        result = self.client.table("source_health").select("*").execute()
        return result.data or []

    def last_successful_scrape(self) -> datetime | None:
        result = (
            self.client.table("scrape_runs")
            .select("ended_at")
            .in_("status", ["success", "partial"])
            .order("ended_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows or not rows[0].get("ended_at"):
            return None
        return datetime.fromisoformat(rows[0]["ended_at"])

    def last_digest_at(self) -> datetime | None:
        result = (
            self.client.table("digest_runs")
            .select("generated_at")
            .eq("delivery_status", "sent")
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows or not rows[0].get("generated_at"):
            return None
        return datetime.fromisoformat(rows[0]["generated_at"])

    def ping(self) -> dict[str, Any]:
        jobs = self.client.table("jobs").select("id", count="exact").limit(1).execute()
        health = self.client.table("source_health").select("source").limit(1).execute()
        return {
            "ok": True,
            "backend": "supabase",
            "schema_jobs": True,
            "schema_source_health": health is not None,
            "count": getattr(jobs, "count", None),
        }

    def expire_jobs(self, missing_streak: int = 3) -> int:
        today = utcnow().date().isoformat()
        result = (
            self.client.table("jobs")
            .update({"active": False})
            .lt("closing_date", today)
            .eq("active", True)
            .execute()
        )
        return len(result.data or [])


def build_repository(settings: Settings | None = None) -> JobRepository:
    settings = settings or get_settings()
    if settings.has_supabase() and not settings.job_scout_dry_run:
        return SupabaseJobRepository(settings)
    logger.info("Using in-memory job repository (no Supabase credentials or dry-run)")
    return InMemoryJobRepository()


def _job_row(job: CanonicalJobRecord, existing: CanonicalJobRecord | None, now: datetime) -> dict[str, Any]:
    first_seen = (existing.first_seen_at if existing else now)
    return {
        "id": str(existing.id if existing and existing.id else job.id or uuid4()),
        "canonical_fingerprint": job.canonical_fingerprint,
        "title": job.title,
        "company": job.company,
        "company_normalised": job.company_normalised,
        "description": job.description,
        "location_text": job.location_text,
        "city": job.city,
        "region": job.region,
        "country_code": job.country_code,
        "work_mode": job.work_mode.value,
        "remote_scope": job.remote_scope.value,
        "salary_min": _jsonable(job.salary.min_amount),
        "salary_max": _jsonable(job.salary.max_amount),
        "salary_currency": job.salary.currency,
        "salary_period": job.salary.period,
        "salary_min_monthly": _jsonable(job.salary.min_monthly),
        "salary_max_monthly": _jsonable(job.salary.max_monthly),
        "salary_usd_monthly": _jsonable(job.salary.usd_monthly),
        "salary_published": job.salary.published,
        "salary_text": job.salary.raw_text,
        "date_posted": job.date_posted.isoformat() if job.date_posted else None,
        "closing_date": job.closing_date.isoformat() if job.closing_date else None,
        "first_seen_at": first_seen.isoformat() if first_seen else now.isoformat(),
        "last_seen_at": now.isoformat(),
        "active": job.active,
        "fit_score": job.fit_score,
        "fit_category": job.fit_category.value if job.fit_category else None,
        "score_breakdown": job.score_breakdown.model_dump() if job.score_breakdown else {},
        "fit_reasons": job.fit_reasons,
        "concerns": job.concerns,
        "visa_sponsorship": job.mobility.visa_sponsorship,
        "relocation_assistance": job.mobility.relocation_assistance,
        "work_authorisation_notes": job.mobility.work_authorisation_notes,
        "updated_at": now.isoformat(),
    }


def _json_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: _jsonable(value) for key, value in payload.items() if value is not None}


def _row_to_job(row: dict[str, Any]) -> CanonicalJobRecord:
    from uuid import UUID

    from job_scout.models.enums import RemoteScope
    from job_scout.utils.dates import parse_date, parse_datetime

    salary = SalarySnapshot(
        published=bool(row.get("salary_published")),
        raw_text=row.get("salary_text"),
        min_amount=_dec(row.get("salary_min")),
        max_amount=_dec(row.get("salary_max")),
        currency=row.get("salary_currency"),
        period=row.get("salary_period"),
        min_monthly=_dec(row.get("salary_min_monthly")),
        max_monthly=_dec(row.get("salary_max_monthly")),
        usd_monthly=_dec(row.get("salary_usd_monthly")),
    )
    breakdown = None
    if row.get("score_breakdown"):
        breakdown = ScoreBreakdown(**row["score_breakdown"])
    return CanonicalJobRecord(
        id=UUID(row["id"]) if row.get("id") else None,
        canonical_fingerprint=row["canonical_fingerprint"],
        title=row.get("title") or "",
        company=row.get("company"),
        company_normalised=row.get("company_normalised"),
        description=row.get("description") or "",
        location_text=row.get("location_text"),
        city=row.get("city"),
        region=row.get("region"),
        country_code=row.get("country_code"),
        work_mode=WorkMode(row.get("work_mode") or "unknown"),
        remote_scope=RemoteScope(row.get("remote_scope") or "unknown"),
        salary=salary,
        mobility=MobilityFlags(
            visa_sponsorship=row.get("visa_sponsorship"),
            relocation_assistance=row.get("relocation_assistance"),
            work_authorisation_notes=row.get("work_authorisation_notes"),
            unknown=row.get("visa_sponsorship") is None,
        ),
        date_posted=parse_datetime(row.get("date_posted")),
        closing_date=parse_date(row.get("closing_date")),
        first_seen_at=parse_datetime(row.get("first_seen_at")),
        last_seen_at=parse_datetime(row.get("last_seen_at")),
        active=bool(row.get("active", True)),
        fit_score=row.get("fit_score"),
        fit_category=FitCategory(row["fit_category"]) if row.get("fit_category") else None,
        score_breakdown=breakdown,
        fit_reasons=row.get("fit_reasons") or [],
        concerns=row.get("concerns") or [],
        last_notified_at=parse_datetime(row.get("last_notified_at")),
    )


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))
