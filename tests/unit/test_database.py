from job_scout.orchestration.health_check import run_health
from job_scout.services.database import InMemoryJobRepository
from tests.conftest import canonical_job
from job_scout.models.job import JobSourceRef
from job_scout.models.enums import SourcePreference


def test_memory_health():
    ping = run_health(memory=True)
    assert ping["ok"] is True


def test_upsert_and_digest_candidates():
    repo = InMemoryJobRepository()
    job = canonical_job()
    job.fit_score = 80
    from job_scout.models.enums import FitCategory

    job.fit_category = FitCategory.STRONG
    repo.upsert_job(
        job,
        JobSourceRef(
            source_name="t",
            source_job_id="1",
            source_url="https://example.com/1",
            source_preference=SourcePreference.AGGREGATOR,
        ),
    )
    found = repo.list_digest_candidates(None, 70)
    assert found
