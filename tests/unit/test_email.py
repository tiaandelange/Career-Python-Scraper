from job_scout.models.enums import FitCategory, WorkMode
from job_scout.services.email_digest import render_digest_html, salary_label, select_digest_jobs
from tests.conftest import canonical_job


def test_salary_label_remote_missing():
    job = canonical_job(work_mode=WorkMode.REMOTE)
    job.salary.published = False
    assert "Not published — allowed because role is fully remote" in salary_label(job)


def test_select_skips_already_notified_unchanged(repo=None):
    from job_scout.utils.dates import utcnow

    fresh = canonical_job(title="New Mechanical Engineer", canonical_fingerprint="new-1")
    fresh.fit_score = 85
    fresh.fit_category = FitCategory.STRONG
    stale = canonical_job(title="Old Mechanical Engineer", canonical_fingerprint="old-1")
    stale.fit_score = 85
    stale.fit_category = FitCategory.STRONG
    stale.last_notified_at = utcnow()
    selection = select_digest_jobs([fresh, stale], previous_by_fp={"old-1": stale})
    fps = {j.canonical_fingerprint for j in selection.jobs}
    assert "new-1" in fps
    assert "old-1" not in fps


def test_html_has_three_sections_in_order():
    remote = canonical_job(work_mode=WorkMode.REMOTE, title="Remote PM", canonical_fingerprint="r")
    remote.fit_score = 88
    remote.fit_category = FitCategory.STRONG
    hybrid = canonical_job(work_mode=WorkMode.HYBRID, title="Hybrid ME", canonical_fingerprint="h")
    hybrid.fit_score = 80
    hybrid.fit_category = FitCategory.STRONG
    onsite = canonical_job(work_mode=WorkMode.ONSITE, title="Onsite ME", canonical_fingerprint="o")
    onsite.fit_score = 90
    onsite.fit_category = FitCategory.EXCEPTIONAL
    selection = select_digest_jobs([remote, hybrid, onsite])
    html = render_digest_html(selection, health={"sources_ok": 3, "sources_failed": 0, "last_successful_scrape": "now"})
    r = html.find("REMOTE")
    h = html.find("HYBRID")
    o = html.find("ON-SITE")
    assert r < h < o
    assert "88" in html or "90" in html
    assert "viewport" in html
