from job_scout.adapters.regional.adzuna import AdzunaAdapter


def _item(**kw):
    base = {
        "id": "1",
        "title": "Mechanical Engineer",
        "company": {"display_name": "Acme Water"},
        "location": {"area": ["US", "Texas", "Houston"]},
        "description": "Pumps and pipelines.",
        "redirect_url": "https://www.adzuna.com/land/ad/1",
        "created": "2026-11-15T10:00:00Z",
        "_country": "us",
    }
    base.update(kw)
    return base


def test_predicted_salary_is_ignored():
    raw = AdzunaAdapter({}).parse_job(_item(salary_min=95000, salary_max=95000, salary_is_predicted="1"))
    assert raw.salary_min is None and raw.salary_max is None
    assert raw.salary_currency is None
    assert raw.raw_payload["salary_predicted"] is True


def test_published_salary_is_kept():
    raw = AdzunaAdapter({}).parse_job(_item(salary_min=90000, salary_max=120000, salary_is_predicted="0"))
    assert raw.salary_min == 90000 and raw.salary_max == 120000
    assert raw.salary_currency == "USD" and raw.salary_period == "annual"


def test_fetch_respects_call_cap(monkeypatch):
    from job_scout.adapters import http as http_mod
    from job_scout.adapters.regional import adzuna as adz

    class FakeSettings:
        adzuna_app_id = "id"
        adzuna_app_key = "key"

    calls = []

    def fake_get_json(self, url, **kwargs):
        calls.append(url)
        n = len(calls)
        return {"results": [_item(id=f"{n}-{i}") for i in range(50)]}

    monkeypatch.setattr(adz, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(http_mod.HttpClient, "get_json", fake_get_json)
    adapter = AdzunaAdapter({"max_calls": 5, "max_pages": 3, "searches": {"us": ["a", "b", "c"]}})
    jobs = list(adapter.fetch_jobs())
    assert len(calls) == 5
    assert len(jobs) == 250


def test_no_keys_means_no_calls(monkeypatch):
    from job_scout.adapters.regional import adzuna as adz

    class NoKeys:
        adzuna_app_id = ""
        adzuna_app_key = ""

    monkeypatch.setattr(adz, "get_settings", lambda: NoKeys())
    assert list(AdzunaAdapter({}).fetch_jobs()) == []
