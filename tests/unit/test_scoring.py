from job_scout.models.enums import FitCategory, WorkMode
from job_scout.services.scoring import score_job
from tests.conftest import canonical_job


def test_mechanical_water_scores_high():
    job = canonical_job(
        title="Lead Mechanical Engineer — Dams and Pipelines",
        description="Chief-level mechanical design for water infrastructure, pumps, valves, QA/QC, FIDIC, BOQs, site inspections.",
    )
    scored = score_job(job)
    assert scored.fit_score is not None and scored.fit_score >= 70
    assert scored.fit_category in {FitCategory.GOOD, FitCategory.STRONG, FitCategory.EXCEPTIONAL}
    assert scored.fit_reasons
    assert "great fit" not in " ".join(scored.fit_reasons).lower()


def test_surgeon_scores_low():
    job = canonical_job(
        title="Consultant Surgeon",
        company="City Hospital",
        description="Perform surgery, clinical audits, theatre lists. Medical council registration required.",
    )
    scored = score_job(job)
    assert scored.fit_score is not None and scored.fit_score < 60
    assert scored.fit_category == FitCategory.LOW


def test_accountant_scores_low():
    job = canonical_job(
        title="Senior Accountant",
        description="Prepare IFRS financial statements, tax returns and statutory audits.",
    )
    scored = score_job(job)
    assert scored.fit_score is not None and scored.fit_score < 60


def test_senior_java_architect_penalised():
    job = canonical_job(
        title="Principal Software Engineer / Java Architect",
        description="Deep CS background, distributed systems architect, Java, Kubernetes platform, compiler internals.",
        work_mode=WorkMode.REMOTE,
    )
    scored = score_job(job)
    assert scored.fit_score is not None and scored.fit_score < 70
    assert any("software" in c.lower() for c in scored.concerns)


def test_project_manager_can_score_well():
    job = canonical_job(
        title="Engineering Project Manager",
        description="Deliver EPC water infrastructure projects, contractors, budgets, multidisciplinary teams, FIDIC.",
    )
    scored = score_job(job)
    assert scored.fit_score is not None and scored.fit_score >= 60
