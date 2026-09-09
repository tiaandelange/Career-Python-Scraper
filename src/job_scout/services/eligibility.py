"""Hard gates. Scoring never sees a job that fails these rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from job_scout.config.settings import load_profile, load_salary_policy
from job_scout.models.enums import RemoteScope, WorkMode
from job_scout.models.job import FilterDecision, NormalisedJobRecord, SalarySnapshot
from job_scout.services.fx import FxService
from job_scout.services.geo import in_target_onsite_countries
from job_scout.services.salary import lower_bound_monthly
from job_scout.utils.dates import utcnow


REMOTE_FRIENDLY = {
    RemoteScope.WORLDWIDE,
    RemoteScope.ANYWHERE,
    RemoteScope.GLOBAL,
    RemoteScope.EMEA,
    RemoteScope.AFRICA,
    RemoteScope.SOUTH_AFRICA,
    RemoteScope.UNKNOWN,
}


def floor_for(snapshot: SalarySnapshot, policy: dict[str, Any], fx: FxService | None) -> tuple[Decimal, str, bool]:
    floors = policy.get("currency_floors_monthly") or {}
    currency = (snapshot.currency or "").upper()
    if currency in floors:
        return Decimal(str(floors[currency])), currency, False
    default = policy.get("default_international_floor") or {"currency": "USD", "amount_monthly": 4500}
    usd_floor = Decimal(str(default["amount_monthly"]))
    return usd_floor, "USD", False


def salary_decision(
    work_mode: WorkMode,
    snapshot: SalarySnapshot,
    policy: dict[str, Any],
    fx: FxService | None = None,
) -> FilterDecision:
    rules = policy.get("rules") or {}
    requires_published = (
        (work_mode == WorkMode.ONSITE and rules.get("onsite_requires_published_salary", True))
        or (work_mode == WorkMode.HYBRID and rules.get("hybrid_requires_published_salary", True))
    )
    if snapshot.estimated:
        return FilterDecision(accepted=False, reasons=["salary_estimate_not_employer_published"])
    if requires_published and not snapshot.published:
        return FilterDecision(
            accepted=False,
            reasons=[f"{work_mode.value}_salary_not_published"],
        )
    if work_mode == WorkMode.REMOTE and not snapshot.published:
        return FilterDecision(
            accepted=True,
            flags=["remote_salary_not_published_allowed"],
        )
    if snapshot.published:
        lower = lower_bound_monthly(snapshot)
        if lower is None:
            if work_mode in {WorkMode.ONSITE, WorkMode.HYBRID}:
                return FilterDecision(
                    accepted=False,
                    reasons=["salary_up_to_only_no_valid_lower_bound"],
                )
            return FilterDecision(accepted=True, flags=["remote_salary_max_only"])
        floor, floor_currency, stale = floor_for(snapshot, policy, fx)
        compare = lower
        notes = []
        if stale:
            notes.append("fx_rate_stale")
        if snapshot.currency and snapshot.currency.upper() != floor_currency:
            if fx is None:
                if work_mode == WorkMode.REMOTE:
                    return FilterDecision(accepted=True, flags=["fx_unavailable_salary_not_converted"])
                return FilterDecision(accepted=False, reasons=["fx_unavailable_cannot_compare_salary"])
            try:
                compare, conv_stale = fx.convert(lower, snapshot.currency, floor_currency)
            except Exception:
                if work_mode == WorkMode.REMOTE:
                    return FilterDecision(accepted=True, flags=["fx_unavailable_salary_not_converted"])
                return FilterDecision(accepted=False, reasons=["fx_unavailable_cannot_compare_salary"])
            if conv_stale:
                notes.append("fx_rate_stale")
        if compare < floor:
            return FilterDecision(
                accepted=False,
                reasons=[
                    f"salary_below_floor:{compare} {floor_currency}/month < {floor} {floor_currency}/month"
                ],
                flags=notes,
            )
        return FilterDecision(accepted=True, flags=notes)
    if work_mode == WorkMode.UNKNOWN:
        return FilterDecision(accepted=False, reasons=["unknown_work_mode_requires_review_salary"])
    return FilterDecision(accepted=True)


def geographic_decision(job: NormalisedJobRecord, profile: dict[str, Any]) -> FilterDecision:
    geo_cfg = profile.get("geographic") or {}
    flags: list[str] = []
    if job.work_mode == WorkMode.REMOTE:
        remote_cfg = geo_cfg.get("remote") or {}
        if job.geo.remote_eligibility_unknown and remote_cfg.get("flag_unknown", True):
            flags.append("remote_eligibility_unknown")
        if job.geo.remote_scope in {RemoteScope.US_ONLY, RemoteScope.AUSTRALIA_ONLY} and remote_cfg.get(
            "reject_if_explicitly_excludes_south_africa", True
        ):
            return FilterDecision(
                accepted=False,
                reasons=[f"remote_restricted_to_{job.geo.remote_scope.value}"],
            )
        if job.geo.remote_scope == RemoteScope.EUROPE and remote_cfg.get(
            "reject_if_explicitly_excludes_south_africa", True
        ):
            return FilterDecision(accepted=False, reasons=["remote_restricted_to_europe"])
        if job.geo.remote_scope == RemoteScope.OTHER_RESTRICTED:
            allowed = {"ZA"}
            restricted = {c.upper() for c in job.geo.remote_country_restrictions}
            if restricted and restricted.isdisjoint(allowed) and "ZA" not in restricted:
                if remote_cfg.get("reject_if_explicitly_excludes_south_africa", True):
                    return FilterDecision(
                        accepted=False,
                        reasons=["remote_country_restrictions_exclude_south_africa"],
                        flags=["review_remote_restrictions"],
                    )
        return FilterDecision(accepted=True, flags=flags)
    if job.work_mode in {WorkMode.ONSITE, WorkMode.HYBRID}:
        if not in_target_onsite_countries(job.geo.country_code, profile):
            return FilterDecision(
                accepted=False,
                reasons=[f"country_not_in_target:{job.geo.country_code or 'unknown'}"],
            )
        return FilterDecision(accepted=True, flags=flags)
    return FilterDecision(accepted=False, reasons=["work_mode_unknown"], flags=["work_mode_unknown"])


def validity_decision(job: NormalisedJobRecord, profile: dict[str, Any]) -> FilterDecision:
    hard = profile.get("hard_filters") or {}
    reasons: list[str] = []
    if hard.get("reject_empty_title", True) and not job.title.strip():
        reasons.append("empty_title")
    if hard.get("reject_expired", True) and job.closing_date and job.closing_date < utcnow().date():
        reasons.append("closing_date_passed")
    if reasons:
        return FilterDecision(accepted=False, reasons=reasons)
    return FilterDecision(accepted=True)


def apply_hard_filters(
    job: NormalisedJobRecord,
    *,
    profile: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    fx: FxService | None = None,
) -> FilterDecision:
    profile = profile or load_profile()
    policy = policy or load_salary_policy()
    decisions = [
        validity_decision(job, profile),
        geographic_decision(job, profile),
        salary_decision(job.work_mode, job.salary, policy, fx),
    ]
    reasons: list[str] = []
    flags: list[str] = []
    accepted = True
    for decision in decisions:
        flags.extend(decision.flags)
        if not decision.accepted:
            accepted = False
            reasons.extend(decision.reasons)
    return FilterDecision(accepted=accepted, reasons=reasons, flags=flags)
