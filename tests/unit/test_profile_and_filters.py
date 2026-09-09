from decimal import Decimal

from job_scout.config.settings import load_profile, load_salary_policy
from job_scout.models.enums import RemoteScope, WorkMode
from job_scout.services.eligibility import apply_hard_filters, salary_decision
from job_scout.services.normalisation import normalise_job
from tests.conftest import raw_job


def test_profile_contains_required_families():
    profile = load_profile()
    families = profile["job_families"]
    assert "engineering" in families
    assert "Mechanical Engineer" in families["engineering"]["titles"]
    assert "Farm Manager" in families["operations"]["titles"]
    assert profile["geographic"]["remote"]["origin_anywhere"] is True
    assert "ZA" in profile["geographic"]["onsite_hybrid_countries"]
    assert "US" in profile["geographic"]["onsite_hybrid_countries"]
    assert "AU" in profile["geographic"]["onsite_hybrid_countries"]
    assert "DE" in profile["geographic"]["onsite_hybrid_countries"]


def test_onsite_without_salary_rejected():
    policy = load_salary_policy()
    job = normalise_job(raw_job(salary_text=None, work_mode_hint="onsite"))
    job.salary.published = False
    decision = salary_decision(WorkMode.ONSITE, job.salary, policy)
    assert decision.accepted is False
    assert "onsite_salary_not_published" in decision.reasons[0]


def test_hybrid_without_salary_rejected():
    policy = load_salary_policy()
    job = normalise_job(raw_job(salary_text=None, work_mode_hint="hybrid", location_text="Cape Town"))
    job.salary.published = False
    decision = salary_decision(WorkMode.HYBRID, job.salary, policy)
    assert decision.accepted is False


def test_onsite_below_floor_rejected():
    job = normalise_job(raw_job(salary_text="R60,000–R90,000 per month"))
    decision = apply_hard_filters(job)
    assert decision.accepted is False
    assert any("salary_below_floor" in r for r in decision.reasons)


def test_onsite_at_floor_accepted():
    job = normalise_job(raw_job(salary_text="R70,000–R90,000 per month"))
    decision = apply_hard_filters(job)
    assert decision.accepted is True


def test_remote_missing_salary_allowed():
    job = normalise_job(
        raw_job(
            salary_text=None,
            work_mode_hint="remote",
            location_text="Worldwide",
            description_text="Fully remote mechanical design engineer. Dams and pipelines.",
        )
    )
    decision = apply_hard_filters(job)
    assert decision.accepted is True
    assert "remote_salary_not_published_allowed" in decision.flags


def test_remote_below_floor_rejected():
    job = normalise_job(
        raw_job(
            salary_text="$2,000 per month",
            work_mode_hint="remote",
            location_text="Worldwide",
            description_text="Fully remote worldwide mechanical engineer.",
        )
    )
    decision = apply_hard_filters(job)
    assert decision.accepted is False


def test_us_only_remote_rejected():
    job = normalise_job(
        raw_job(
            salary_text=None,
            work_mode_hint="remote",
            location_text="Remote – US residents only",
            description_text="This role is remote. US residents only. Mechanical engineer.",
        )
    )
    assert job.geo.remote_scope == RemoteScope.US_ONLY
    decision = apply_hard_filters(job)
    assert decision.accepted is False


def test_never_invent_salary():
    job = normalise_job(raw_job(salary_text=None, work_mode_hint="remote", location_text="Worldwide"))
    assert job.salary.published is False
    assert job.salary.min_monthly is None
    assert job.salary.min_amount is None


def test_unknown_country_onsite_rejected():
    job = normalise_job(
        raw_job(
            location_text="Singapore",
            work_mode_hint="onsite",
            salary_text="SGD 12000 per month",
        )
    )
    decision = apply_hard_filters(job)
    assert decision.accepted is False
    assert any("country_not_in_target" in r for r in decision.reasons)
