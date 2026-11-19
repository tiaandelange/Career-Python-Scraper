"""PERM sponsor list, its effect on scoring/dashboard, and CI-skipped sources."""

from __future__ import annotations

import pytest

from job_scout.models.enums import WorkMode
from job_scout.services import sponsors
from tests.conftest import canonical_job


@pytest.fixture
def sponsor_csv(tmp_path, monkeypatch):
    from job_scout.config import settings as settings_mod

    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "visa_sponsors.csv").write_text(
        "employer_key,employer,engineering_certified,total_certified\n"
        "black and veatch,BLACK & VEATCH CORPORATION,14,20\n"
        "fervo energy,Fervo Energy Company,3,3\n",
        encoding="utf-8",
    )
    real = settings_mod.get_settings()
    monkeypatch.setattr(type(real), "config_dir", lambda self: cfg)
    sponsors.clear_cache()
    yield cfg
    sponsors.clear_cache()


@pytest.mark.parametrize(
    "raw,key",
    [
        ("Black & Veatch Corporation", "black and veatch"),
        ("BLACK AND VEATCH, INC.", "black and veatch"),
        ("The Fervo Energy Company LLC", "fervo energy"),
        ("Xylem Inc.", "xylem"),
        ("", ""),
    ],
)
def test_employer_key(raw, key):
    assert sponsors.employer_key(raw) == key


def test_lookup_exact_prefix_and_miss(sponsor_csv):
    assert sponsors.lookup("Black & Veatch").engineering_certified == 14
    assert sponsors.lookup("Black & Veatch Holding Company").engineering_certified == 14
    assert sponsors.lookup("Fervo Energy").engineering_certified == 3
    assert sponsors.lookup("Black") is None  # never match on a single word
    assert sponsors.lookup("Unknown Water Co") is None


def test_lookup_without_file_is_none(tmp_path, monkeypatch):
    from job_scout.config import settings as settings_mod

    monkeypatch.setattr(type(settings_mod.get_settings()), "config_dir", lambda self: tmp_path)
    sponsors.clear_cache()
    assert sponsors.lookup("Black & Veatch") is None
    sponsors.clear_cache()


def test_build_sponsor_csv_from_xlsx(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["CASE_NUMBER", "CASE_STATUS", "EMPLOYER_NAME", "EMPLOYER_POC_FIRST_NAME", "PW_SOC_CODE", "PW_SOC_TITLE"])
    ws.append(["A-1", "Certified", "Black & Veatch Corporation", "Pat", "17-2141", "Mechanical Engineers"])
    ws.append(["A-2", "Certified-Expired", "BLACK AND VEATCH CORP", "Pat", "17-2051", "Civil Engineers"])
    ws.append(["A-3", "Denied", "Black & Veatch Corporation", "Pat", "17-2141", "Mechanical Engineers"])
    ws.append(["A-4", "Certified", "Software Only LLC", "Sam", "15-1252", "Software Developers"])
    src = tmp_path / "perm.xlsx"
    wb.save(src)
    out = tmp_path / "visa_sponsors.csv"
    stats = sponsors.build_sponsor_csv([src], out)
    text = out.read_text(encoding="utf-8")
    assert stats == {"rows_read": 4, "employers_certified": 2, "engineering_sponsors": 1}
    assert "black and veatch," in text and ",2,2" in text
    assert "software only" not in text  # no engineering certifications


def test_sponsor_history_boosts_us_jobs_only(sponsor_csv):
    from job_scout.services.scoring import sponsor_history

    us = canonical_job(work_mode=WorkMode.ONSITE)
    us.company, us.country_code = "Black & Veatch", "US"
    assert sponsor_history(us).engineering_certified == 14

    za = canonical_job(work_mode=WorkMode.ONSITE)
    za.company, za.country_code = "Black & Veatch", "ZA"
    assert sponsor_history(za) is None

    remote = canonical_job(work_mode=WorkMode.REMOTE)
    remote.company, remote.country_code = "Black & Veatch", "US"
    assert sponsor_history(remote) is None

    refuses = canonical_job(work_mode=WorkMode.ONSITE)
    refuses.company, refuses.country_code = "Black & Veatch", "US"
    refuses.mobility.visa_sponsorship = False
    assert sponsor_history(refuses) is None


def test_dashboard_marks_sponsor_history(sponsor_csv):
    from job_scout.services.dashboard import job_to_card

    job = canonical_job(work_mode=WorkMode.ONSITE)
    job.company, job.country_code, job.fit_score = "Fervo Energy", "US", 80
    card = job_to_card(job)
    assert card["visa"] == "history" and card["perm"] == 3


def test_skip_in_ci_sources(monkeypatch):
    from job_scout.adapters import registry

    cfg = {
        "sources": {
            "blocked": {"enabled": True, "skip_in_ci": True, "pipelines": ["onsite"], "adapter": "job_scout.adapters.regional.dws_vacancies:DwsVacanciesAdapter"},
            "fine": {"enabled": True, "pipelines": ["onsite"], "adapter": "job_scout.adapters.regional.dws_vacancies:DwsVacanciesAdapter"},
            "off": {"enabled": False, "pipelines": ["onsite"], "adapter": "x:y"},
        }
    }

    class S:
        def __init__(self, env):
            self.job_scout_env = env

    monkeypatch.setattr(registry, "get_settings", lambda: S("github"))
    assert [a.config["name"] for a in registry.iter_adapters(pipeline="onsite", sources_config=cfg)] == ["fine"]
    assert registry.inactive_source_names(cfg) == {"blocked", "off"}
    monkeypatch.setattr(registry, "get_settings", lambda: S("local"))
    assert len(registry.iter_adapters(pipeline="onsite", sources_config=cfg)) == 2
    assert registry.inactive_source_names(cfg) == {"off"}
