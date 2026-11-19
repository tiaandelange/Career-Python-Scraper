"""Electrical / controls titles are excluded; mechanical, QA/QC, inspection and civil are kept."""

import pytest

from job_scout.config.settings import load_profile
from job_scout.pipelines.common import is_family_relevant, title_excluded

PROFILE = load_profile()
WATER_BODY = "Water infrastructure plant with pumps, valves and pipelines."


@pytest.mark.parametrize(
    "title",
    [
        "Staff Electrical Engineer",
        "Senior Instrumentation and Controls Engineer",
        "Senior Nuclear I&C Engineer – Hardware",
        "SCADA Controls Automation Project Engineer",
        "Substation Protection and Control Engineer, EPC",
        "Power Electronics Engineer, Energy Storage",
        "Lead Electrician, Test Facilities",
        "Senior Technical Product Manager, Internal Software",
        "Senior Plant Control Systems Engineer, Motion Control",
        "Project Manager - Power Delivery",
        "Senior Staff Commissioning Engineer, Electrical",
    ],
)
def test_other_disciplines_excluded_even_with_water_words(title):
    assert title_excluded(title, PROFILE)
    assert not is_family_relevant(title, WATER_BODY, PROFILE)


@pytest.mark.parametrize(
    "title",
    [
        "Senior Mechanical Engineer",
        "Mechanical Design Engineer, Power Conversion",
        "Senior Mechanical Engineer - Thermophotovoltaic Hardware & Manufacturing",
        "Electrical & Mechanical Inspector",
        "Lead Project Controls Specialist, EPC",
        "Staff Quality Control (QC) Engineer",
        "Construction Quality Assurance/Quality Control Manager, EPC",
        "QA/QC Manager",
        "Source Inspector",
        "Welding Inspector",
        "Senior Civil Engineer",
        "Water Resources Engineer",
        "Resident Engineer",
        "Dam Safety Engineer",
    ],
)
def test_target_disciplines_kept_and_relevant(title):
    assert not title_excluded(title, PROFILE)
    assert is_family_relevant(title, "", PROFILE)
