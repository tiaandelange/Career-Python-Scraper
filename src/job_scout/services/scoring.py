"""Explainable 0–100 fit scoring. No paid LLM."""

from __future__ import annotations

import re
from typing import Any

from job_scout.config.settings import load_profile, load_scoring
from job_scout.models.enums import FitCategory, RemoteScope, WorkMode
from job_scout.models.job import CanonicalJobRecord, ScoreBreakdown
from job_scout.utils.text import normalise_key


def _hits(blob: str, phrases: list[str]) -> list[str]:
    found = []
    for phrase in phrases:
        key = normalise_key(phrase)
        if not key:
            continue
        if len(key) <= 3:
            if re.search(rf"\b{re.escape(key)}\b", blob):
                found.append(phrase)
        elif key in blob:
            found.append(phrase)
    return found


def _scale(hits: int, cap: int, weight: float) -> float:
    if cap <= 0:
        return 0.0
    return min(1.0, hits / cap) * weight


def category_for(score: int, scoring: dict[str, Any]) -> FitCategory:
    bands = scoring.get("categories") or {}
    for name, bounds in bands.items():
        low, high = bounds
        if low <= score <= high:
            return FitCategory(name)
    return FitCategory.LOW


def score_job(
    job: CanonicalJobRecord,
    *,
    profile: dict[str, Any] | None = None,
    scoring: dict[str, Any] | None = None,
) -> CanonicalJobRecord:
    profile = profile or load_profile()
    scoring = scoring or load_scoring()
    weights = scoring.get("weights") or {}
    blob = normalise_key(f"{job.title}\n{job.company or ''}\n{job.description}\n{job.location_text or ''}")
    title = normalise_key(job.title)
    reasons: list[str] = []
    concerns: list[str] = []
    breakdown = ScoreBreakdown()

    prof_hits = _hits(blob, scoring.get("professional_positive") or [])
    breakdown.professional_relevance = _scale(len(prof_hits), 5, float(weights.get("professional_relevance", 25)))
    if prof_hits:
        reasons.append(f"Mechanical/infrastructure language matches your background: {', '.join(prof_hits[:4])}.")

    skill_hits = _hits(blob, scoring.get("skills_positive") or [])
    breakdown.skills = _scale(len(skill_hits), 4, float(weights.get("skills", 18)))
    if skill_hits:
        reasons.append(f"Required methods overlap your practice: {', '.join(skill_hits[:4])}.")

    sen_hits = _hits(blob, scoring.get("seniority_positive") or [])
    breakdown.seniority = _scale(max(len(sen_hits), 1 if "engineer" in title else 0), 2, float(weights.get("seniority", 8)))
    if sen_hits:
        reasons.append(f"Seniority ({', '.join(sen_hits)}) aligns with acting Chief Engineer / design leadership.")

    sector_hits = _hits(blob, scoring.get("sectors_high") or [])
    breakdown.sector = _scale(len(sector_hits), 3, float(weights.get("sector", 12)))
    if sector_hits:
        reasons.append(f"Sector fit: {', '.join(sector_hits[:3])}.")

    lead_hits = _hits(blob, scoring.get("leadership_positive") or [])
    breakdown.leadership_pm = _scale(len(lead_hits), 3, float(weights.get("leadership_pm", 10)))
    if lead_hits:
        reasons.append(f"Leadership/delivery overlap: {', '.join(lead_hits[:3])}.")

    digital_hits = _hits(blob, scoring.get("digital_positive") or [])
    overclaim = _hits(blob, scoring.get("digital_overclaim_penalties") or [])
    digital_weight = float(weights.get("digital_transferability", 6))
    if overclaim and not digital_hits:
        breakdown.digital_transferability = 0
        breakdown.penalties += 25
        concerns.append(
            "Advert asks for specialist software-engineering experience "
            f"({', '.join(overclaim[:3])}) beyond AI-assisted / web / automation transfer."
        )
    else:
        breakdown.digital_transferability = _scale(len(digital_hits), 3, digital_weight)
        if overclaim:
            breakdown.penalties += 12
            concerns.append(
                f"Software specialism still listed ({', '.join(overclaim[:2])}); treat digital fit as transferable, not equivalent."
            )
        elif digital_hits:
            reasons.append(f"Transferable digital skills apply: {', '.join(digital_hits[:3])}.")

    ops_hits = _hits(blob, scoring.get("operations_positive") or [])
    breakdown.operations_alt = _scale(len(ops_hits), 2, float(weights.get("operations_alt", 6)))
    if ops_hits:
        reasons.append(f"Operations/property transfer: {', '.join(ops_hits[:3])}.")

    unrelated = _hits(title, scoring.get("unrelated_roles") or []) + _hits(blob, scoring.get("unrelated_roles") or [])
    if unrelated:
        breakdown.penalties += 40
        concerns.append(f"Core occupation appears unrelated ({', '.join(unrelated[:2])}).")

    # Compensation above floor (already gated).
    comp_weight = float(weights.get("compensation", 7))
    multiple = None
    if job.salary.min_monthly and job.salary.currency:
        floors = {"ZAR": 70000.0, "USD": 4500.0, "EUR": 4000.0}
        floor = floors.get(job.salary.currency.upper())
        if floor:
            multiple = float(job.salary.min_monthly) / floor
    if multiple is None and job.salary.usd_monthly:
        multiple = float(job.salary.usd_monthly) / 4500.0
    if multiple is not None:
        breakdown.compensation = min(comp_weight, 4.0 + max(0.0, multiple - 1.0) * 6.0)
        reasons.append("Employer-published salary meets or exceeds the configured floor.")
    elif job.work_mode == WorkMode.REMOTE and not job.salary.published:
        breakdown.compensation = 2.0
        concerns.append("Salary not published — allowed because the role is fully remote.")

    wm_boost = scoring.get("work_mode_boost") or {}
    if job.work_mode == WorkMode.REMOTE and job.remote_scope in {
        RemoteScope.WORLDWIDE,
        RemoteScope.ANYWHERE,
        RemoteScope.GLOBAL,
        RemoteScope.EMEA,
        RemoteScope.AFRICA,
        RemoteScope.SOUTH_AFRICA,
    }:
        breakdown.work_mode = float(wm_boost.get("remote_global", 5))
        reasons.append("Fully remote with geographic eligibility compatible with working from South Africa.")
    elif job.work_mode == WorkMode.REMOTE:
        breakdown.work_mode = float(wm_boost.get("remote_unknown", 1))
    elif job.work_mode == WorkMode.HYBRID:
        breakdown.work_mode = float(wm_boost.get("hybrid", 1))

    if job.mobility.visa_sponsorship:
        breakdown.international_mobility += float((scoring.get("mobility_boost") or {}).get("visa_sponsorship", 8))
        reasons.append("Employer states visa sponsorship is available.")
    if job.mobility.relocation_assistance:
        breakdown.international_mobility += float((scoring.get("mobility_boost") or {}).get("relocation", 5))
        reasons.append("Relocation assistance is mentioned.")
    if job.mobility.citizenship_required:
        breakdown.international_mobility -= float((scoring.get("mobility_penalty") or {}).get("citizenship_required", 18))
        concerns.append("Citizenship is explicitly required; you should not assume eligibility.")
    if job.mobility.work_right_required:
        breakdown.international_mobility -= float(
            (scoring.get("mobility_penalty") or {}).get("unrestricted_work_rights", 14)
        )
        concerns.append("Existing local work rights are required; sponsorship is not implied.")
    if job.mobility.unknown:
        concerns.append("Visa/work-authorisation status is unknown — not assumed.")

    families = (profile.get("job_families") or {})
    family_hit = False
    family_weight = 0.0
    for spec in families.values():
        titles = [normalise_key(t) for t in spec.get("titles") or []]
        keywords_hit = any(normalise_key(k) in blob for k in spec.get("keywords") or [])
        title_hit = any(t and t in title for t in titles)
        if title_hit or keywords_hit:
            family_hit = True
            family_weight = max(family_weight, float(spec.get("weight") or 0.5))
    if family_hit:
        breakdown.professional_relevance = max(
            breakdown.professional_relevance,
            float(weights.get("professional_relevance", 25)) * min(1.0, family_weight),
        )
    elif breakdown.professional_relevance < 8:
        concerns.append("Title/description is only weakly related to configured job families.")

    total = (
        breakdown.professional_relevance
        + breakdown.skills
        + breakdown.seniority
        + breakdown.sector
        + breakdown.leadership_pm
        + breakdown.digital_transferability
        + breakdown.operations_alt
        + breakdown.compensation
        + breakdown.work_mode
        + max(breakdown.international_mobility, -20)
        - breakdown.penalties
    )
    score = int(max(0, min(100, round(total))))
    core_titles = (
        "mechanical engineer",
        "mechanical design",
        "water engineer",
        "pipeline engineer",
        "chief engineer",
        "design engineer",
        "rotating equipment",
    )
    if any(token in title for token in core_titles) and breakdown.sector >= 4 and breakdown.penalties < 10:
        score = max(score, 78)
    job.fit_score = score
    job.fit_category = category_for(score, scoring)
    job.score_breakdown = breakdown
    job.fit_reasons = reasons[:5] or ["Limited direct overlap with the advertised requirements."]
    job.concerns = concerns[:5]
    return job
