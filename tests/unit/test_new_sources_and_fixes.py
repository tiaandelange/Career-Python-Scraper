"""New sources (SuccessFactors RSS, YM Careers, Oracle CX, SR searches) and the fixes they exposed."""

from __future__ import annotations

import pytest

from job_scout.config.settings import load_profile
from job_scout.models.enums import SourceType
from job_scout.models.job import RawJobRecord
from job_scout.pipelines.common import employer_excluded, title_excluded
from job_scout.services.geo import country_from_text, geo_from_raw
from job_scout.services.mobility import extract_mobility

PROFILE = load_profile()


def _raw(**kw) -> RawJobRecord:
    base = dict(source_name="t", source_type=SourceType.API, source_job_id="1", source_url="https://x/1", title="Mechanical Engineer")
    base.update(kw)
    return RawJobRecord(**base)


# --- visa / relocation fields --------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Company : Black & Veatch Relocation eligible : No Visa Sponsorship Available: No Why us?", False),
        ("Visa sponsorship available: Yes", True),
        ("Sponsorship available - no", False),
    ],
)
def test_structured_visa_field_wins(text, expected):
    assert extract_mobility("Engineer", text, _raw()).visa_sponsorship is expected


def test_structured_relocation_field():
    flags = extract_mobility("Engineer", "Relocation eligible : No. Visa Sponsorship Available: No", _raw())
    assert flags.relocation_assistance is False


# --- geography ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,code",
    [
        ("Pune, MH, IN", "IN"),
        ("Overland Park, KS, US", "US"),
        ("Brisbane, Queensland, AU", "AU"),
        ("Atlanta, GA", "US"),
        ("Leeds, UK, UK", "GB"),
    ],
)
def test_country_from_city_state_country(text, code):
    assert country_from_text(text) == code


def test_structured_country_hint_beats_state_lookalikes():
    for loc, cc in (("Bangalore, in", "in"), ("Bogota, co", "co")):
        snap = geo_from_raw(_raw(location_text=loc, raw_payload={"country_code": cc}), "")
        assert snap.country_code == cc.upper()


# --- discipline / employer filters ------------------------------------------------------------


@pytest.mark.parametrize(
    "title",
    [
        "Assistant Professor – Mechanical Engineering",
        "Department Head, Mechanical Engineering",
        "Instrument & Controls Intern - Water",
        "Graduate Mechanical Engineer",
        "Early Career Mechanical Engineer",
        "Mechanical Engineering - AI Model Evaluator",
    ],
)
def test_always_excluded_titles(title):
    assert title_excluded(title, PROFILE)


def test_senior_mechanical_still_kept():
    assert not title_excluded("Senior Mechanical Engineer, HVAC", PROFILE)


@pytest.mark.parametrize("company,blocked", [("SpaceX", True), ("Space Exploration Technologies Corp.", True),
                                             ("Lockheed Martin", True), ("Black & Veatch", False),
                                             ("Spacecraft Water Co", False)])
def test_employer_excluded(company, blocked):
    assert employer_excluded(company, PROFILE) is blocked


# --- adapters ---------------------------------------------------------------------------------


def test_successfactors_title_location_split():
    from job_scout.adapters.ats.successfactors_rss import SuccessFactorsRssAdapter, split_title_location

    assert split_title_location("Senior Piping Engineer (Brisbane, Queensland, AU)") == (
        "Senior Piping Engineer",
        "Brisbane, Queensland, AU",
    )
    raw = SuccessFactorsRssAdapter({}).parse_job(
        {"title": "Mechanical Engineer (Overland Park, KS, US)", "link": "https://careers.bv.com/job/1",
         "summary": "<p>Pumps</p>", "_company": "Black & Veatch", "_slug": "blackveatch"}
    )
    assert raw.title == "Mechanical Engineer" and raw.location_text == "Overland Park, KS, US"
    assert raw.source_name == "successfactors:blackveatch"


def test_ym_careers_parse():
    from job_scout.adapters.regional.ym_careers import YmCareersAdapter

    raw = YmCareersAdapter({}).parse_job(
        {"title": "Principal Mechanical Engineer - NPD | Tennant Company",
         "link": "https://careers.nspe.org/jobs/rss/22694606/principal-mechanical-engineer-npd",
         "summary": "Golden Valley, Minnesota,  With more than $1B in revenue...", "_board": "nspe"}
    )
    assert raw.title == "Principal Mechanical Engineer - NPD"
    assert raw.company == "Tennant Company"
    assert raw.location_text == "Golden Valley, Minnesota"
    assert raw.source_job_id == "22694606"


def test_oracle_parse():
    from job_scout.adapters.ats.oracle_cx import OracleCxAdapter

    emp = {"name": "GHD", "slug": "ghd", "host": "ejov.fa.ca2.oraclecloud.com", "site": "CX"}
    raw = OracleCxAdapter({}).parse_job(
        {"Id": "28601", "Title": "Senior Mechanical Engineer, HVAC", "PrimaryLocation": "MELBOURNE, VICTORIA, Australia",
         "PrimaryLocationCountry": "AU", "PostedDate": "2026-11-16", "WorkplaceType": "Hybrid",
         "ExternalDescriptionStr": "<p>HVAC design</p>", "_emp": emp}
    )
    assert raw.apply_url.endswith("/sites/CX/job/28601")
    assert raw.work_mode_hint == "hybrid"
    assert geo_from_raw(raw, "").country_code == "AU"


def test_smartrecruiters_keyword_searches_dedupe(monkeypatch):
    from job_scout.adapters import http as http_mod
    from job_scout.adapters.ats import smartrecruiters as sr

    calls = []

    def fake_get_json(self, url, params=None, **kw):
        calls.append(dict(params or {}))
        if "/postings/" in url:
            return {"jobAd": {"sections": {"jobDescription": {"text": "Inspect welds"}}}}
        # Both searches return the same posting: it must be yielded once.
        return {"content": [{"id": "A1", "name": "Welding Inspector", "location": {"city": "Omaha", "countryCode": "us"}}]}

    monkeypatch.setattr(http_mod.HttpClient, "get_json", fake_get_json)
    monkeypatch.setattr(sr, "_title_filter", lambda: (lambda _t: True))
    adapter = sr.SmartRecruitersAdapter(
        {"employers": [{"name": "SGS", "slug": "sgs", "queries": ["inspector", "welding"], "countries": ["us"]}]}
    )
    jobs = list(adapter.fetch_jobs())
    assert len(jobs) == 1
    assert {c.get("q") for c in calls if "q" in c} == {"inspector", "welding"}
    assert all(c.get("country") == "us" for c in calls if "q" in c)
    assert jobs[0].raw_payload["country_code"] == "us"


# --- freshness ---------------------------------------------------------------------------------


def test_freshness_adjustment():
    from datetime import timedelta

    from job_scout.config.settings import load_scoring
    from job_scout.services.scoring import freshness_adjustment
    from job_scout.utils.dates import utcnow
    from tests.conftest import canonical_job

    scoring = load_scoring()
    job = canonical_job()
    job.closing_date = None
    job.date_posted = utcnow() - timedelta(days=2)
    assert freshness_adjustment(job, scoring)[0] == 3
    job.date_posted = utcnow() - timedelta(days=45)
    assert freshness_adjustment(job, scoring)[0] == -4
    job.date_posted = utcnow() - timedelta(days=90)
    assert freshness_adjustment(job, scoring)[0] == -10
    job.closing_date = (utcnow() + timedelta(days=5)).date()  # explicitly still open
    assert freshness_adjustment(job, scoring)[0] == 0
    job.date_posted = None
    assert freshness_adjustment(job, scoring)[0] == 0


# --- dashboard grouping --------------------------------------------------------------------------


def test_group_locations_merges_multi_city_postings():
    from job_scout.services.dashboard import group_locations

    base = {"title": "Industrial Mechanical Engineer", "company": "AECOM", "firstSeen": "2026-11-19", "score": 70}
    cards = [
        {**base, "location": "Greenville", "score": 70},
        {**base, "location": "Charlotte", "score": 75, "firstSeen": "2026-11-10"},
        {**base, "location": "Raleigh"},
        {"title": "Other", "company": "AECOM", "location": "X", "firstSeen": None, "score": 60},
    ]
    out = group_locations(cards)
    assert len(out) == 2
    main = next(c for c in out if c["title"].startswith("Industrial"))
    assert main["location"] == "Charlotte" and main["score"] == 75
    assert sorted(main["otherLocations"]) == ["Greenville", "Raleigh"]
    assert main["firstSeen"] == "2026-11-10"
