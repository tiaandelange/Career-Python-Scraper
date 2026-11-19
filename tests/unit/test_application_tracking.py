"""Application tracking: dashboard config, email behaviour and the job_status security policy."""

from __future__ import annotations

import json
import re
from pathlib import Path

from job_scout.models.enums import FitCategory
from tests.conftest import canonical_job


def _meta(html: str) -> dict:
    return json.loads(re.search(r"const META = (\{.*?\});\n", html, re.S).group(1).replace("\\u003c", "<"))


def test_dashboard_embeds_tracking_only_when_configured(tmp_path):
    from job_scout.services.dashboard import build_dashboard

    job = canonical_job(canonical_fingerprint="a")
    job.fit_score, job.fit_category = 80, FitCategory.STRONG
    build_dashboard([job], tmp_path / "plain", min_score=60)
    assert _meta((tmp_path / "plain" / "index.html").read_text(encoding="utf-8"))["tracking"] is None

    build_dashboard([job], tmp_path / "tracked", min_score=60, tracking={"url": "https://x.supabase.co", "key": "anon"})
    html = (tmp_path / "tracked" / "index.html").read_text(encoding="utf-8")
    assert _meta(html)["tracking"] == {"url": "https://x.supabase.co", "key": "anon"}
    assert "supabase-js@2.45.4" in html and "job_status" in html


def test_email_skips_tracked_jobs_and_shows_pipeline():
    from job_scout.config.settings import Settings
    from job_scout.services.database import InMemoryJobRepository
    from job_scout.services.email_digest import build_and_maybe_send

    repo = InMemoryJobRepository()
    for fp, title in (("applied-1", "Applied Mechanical Engineer"), ("fresh-1", "Fresh Mechanical Engineer")):
        job = canonical_job(canonical_fingerprint=fp, title=title)
        job.fit_score, job.fit_category = 85, FitCategory.STRONG
        repo.jobs[fp] = job
    repo.job_statuses = {"applied-1": "applied", "gone-1": "interviewing"}
    result = build_and_maybe_send(repo, settings=Settings(dashboard_url="https://d/"), send=False)
    assert result["jobs"] == ["fresh-1"]
    assert "Applied Mechanical Engineer" not in result["html"]
    assert "Your applications:" in result["html"] and "1 applied" in result["html"] and "1 interviewing" in result["html"]


def test_migration_locks_rows_to_owner():
    sql = Path("supabase/migrations/0005_job_status.sql").read_text(encoding="utf-8").lower()
    assert "enable row level security" in sql
    for action in ("select", "insert", "update", "delete"):
        assert re.search(rf"for {action} to authenticated", sql)
    assert sql.count("user_id = auth.uid()") >= 5
    assert "revoke all on public.job_status from anon" in sql
