from decimal import Decimal

from job_scout.config.settings import load_profile, load_salary_policy
from job_scout.models.enums import SourcePreference, SourceType, WorkMode
from job_scout.models.job import GeoSnapshot, MobilityFlags, NormalisedJobRecord, RawJobRecord, SalarySnapshot
from job_scout.pipelines.common import is_family_relevant
from job_scout.services.eligibility import apply_hard_filters, salary_decision
from job_scout.services.geo import country_from_text
from job_scout.services.work_mode import classify_work_mode


def test_family_matches_inverted_dpsa_title():
    profile = load_profile()
    assert is_family_relevant("ENGINEER (MECHANICAL)", "", profile)
    assert is_family_relevant("CIVIL/ STRUCTURAL ENGINEER", "infrastructure delivery", profile)


def test_unknown_not_coerced_via_remote_board_hint_with_city():
    mode = classify_work_mode(
        title="Mechanical Engineer",
        description="Design piping systems for water plants.",
        location="Cape Town, South Africa",
        source_hint="remote",
    )
    assert mode == WorkMode.UNKNOWN


def test_remote_hint_still_works_when_location_says_remote():
    mode = classify_work_mode(
        title="Mechanical Engineer",
        description="WFH role",
        location="Remote – EMEA",
        source_hint="remote",
    )
    assert mode == WorkMode.REMOTE


def test_sa_generic_centres_resolve_to_za():
    assert country_from_text("Head Office") is None  # not global ZA — DPSA-scoped via geo_from_raw
    assert country_from_text("Gauteng") == "ZA"
    assert country_from_text("Polokwane") == "ZA"
    from job_scout.services.geo import geo_from_raw

    raw = RawJobRecord(
        source_name="dpsa_circular",
        source_type=SourceType.HTML,
        source_job_id="1",
        source_url="https://www.dpsa.gov.za/x.pdf#post-1",
        title="Engineer",
        company="Department of Water and Sanitation",
        location_text="Head Office",
        source_preference=SourcePreference.GOVERNMENT,
    )
    assert geo_from_raw(raw, "").country_code == "ZA"

def test_dpsa_annual_uses_public_service_floor():
    policy = load_salary_policy()
    snap = SalarySnapshot(
        published=True,
        currency="ZAR",
        period="annual",
        min_amount=Decimal("389145"),
        max_amount=Decimal("589015"),
        min_monthly=Decimal("32428.75"),
        max_monthly=Decimal("49084.58"),
        raw_text="R389145 - R589015 per annum",
    )
    ok = salary_decision(WorkMode.ONSITE, snap, policy, source_name="dpsa_circular")
    assert ok.accepted
    assert "public_service_annual_floor" in ok.flags

    low = SalarySnapshot(
        published=True,
        currency="ZAR",
        period="annual",
        min_amount=Decimal("200000"),
        min_monthly=Decimal("16666.67"),
        raw_text="R200000 per annum",
    )
    bad = salary_decision(WorkMode.ONSITE, low, policy, source_name="dpsa_circular")
    assert not bad.accepted


def test_dpsa_head_office_clears_geo_gate():
    profile = load_profile()
    policy = load_salary_policy()
    raw = RawJobRecord(
        source_name="dpsa_circular",
        source_type=SourceType.HTML,
        source_job_id="2026-32/252",
        source_url="https://www.dpsa.gov.za/x.pdf#post-32/252",
        title="CHIEF ENGINEER, GRADE A",
        company="Department of Water and Sanitation",
        source_preference=SourcePreference.GOVERNMENT,
    )
    job = NormalisedJobRecord(
        raw=raw,
        title=raw.title,
        company=raw.company,
        description="Water infrastructure and dam safety.",
        work_mode=WorkMode.ONSITE,
        salary=SalarySnapshot(
            published=True,
            currency="ZAR",
            period="annual",
            min_amount=Decimal("945495"),
            min_monthly=Decimal("78791.25"),
            raw_text="R945495 per annum",
        ),
        mobility=MobilityFlags(),
        geo=GeoSnapshot(country_code="ZA", country_name="South Africa"),
        fingerprint="test-fp",
    )
    decision = apply_hard_filters(job, profile=profile, policy=policy)
    assert decision.accepted
