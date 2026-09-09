from job_scout.models.enums import RemoteScope
from job_scout.services.geo import classify_remote_scope, country_from_text


def test_country_aliases():
    assert country_from_text("Cape Town, South Africa") == "ZA"
    assert country_from_text("Denver, United States") == "US"
    assert country_from_text("Sydney, Australia") == "AU"
    assert country_from_text("Berlin, Germany") == "DE"


def test_worldwide_scope():
    geo = classify_remote_scope("Worldwide", "Work from anywhere in the world.", [], [])
    assert geo.remote_scope in {RemoteScope.WORLDWIDE, RemoteScope.ANYWHERE}


def test_us_only_not_silently_global():
    geo = classify_remote_scope("Remote – US residents only", "Must be located in the United States.", [], [])
    assert geo.remote_scope == RemoteScope.US_ONLY
