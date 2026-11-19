"""Adzuna official developer API. Disabled until APP_ID/APP_KEY are set."""

from __future__ import annotations

from typing import Any, Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.config.settings import get_settings
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.utils.dates import parse_datetime
from job_scout.utils.text import strip_html

# Defaults; sources.yaml `searches` overrides them. Free tier: 25 calls/minute, 250/day, so a
# run is capped at `max_calls` (scrape runs 3x a day) and calls are spaced >= 2.5s apart.
DEFAULT_SEARCHES = {
    "us": ["mechanical engineer", "water engineer", "project engineer"],
    "za": ["mechanical engineer"],
}

_COUNTRY_CURRENCY = {
    "za": "ZAR",
    "us": "USD",
    "au": "AUD",
    "de": "EUR",
    "nl": "EUR",
}


def _currency_for_country(country: str | None) -> str:
    return _COUNTRY_CURRENCY.get((country or "").lower(), "USD")


class AdzunaAdapter(SourceAdapter):
    source_name = "adzuna"
    source_type = SourceType.API

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        settings = get_settings()
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            return
        searches: dict[str, list[str]] = self.config.get("searches") or DEFAULT_SEARCHES
        pages = int(self.config.get("max_pages", 2))
        max_calls = int(self.config.get("max_calls", 20))
        delay = max(2.5, float(self.config.get("request_delay_seconds", 2.5)))
        max_days_old = int(self.config.get("max_job_age_days", 30))
        calls = 0
        seen: set[str] = set()
        client = HttpClient()
        try:
            for country, queries in searches.items():
                for what in queries:
                    for page in range(1, pages + 1):
                        if calls >= max_calls:
                            return
                        calls += 1
                        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
                        try:
                            payload = client.get_json(
                                url,
                                params={
                                    "app_id": settings.adzuna_app_id,
                                    "app_key": settings.adzuna_app_key,
                                    "what": what,
                                    "results_per_page": 50,
                                    "max_days_old": max_days_old,
                                    "sort_by": "date",
                                    "content-type": "application/json",
                                },
                                delay=delay,
                            )
                        except Exception:
                            break
                        results = payload.get("results") or []
                        for item in results:
                            key = str(item.get("id") or item.get("redirect_url"))
                            if key in seen:
                                continue
                            seen.add(key)
                            item["_country"] = country
                            try:
                                yield self.parse_job(item)
                            except Exception:
                                continue
                        if len(results) < 50:
                            break
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        loc = payload.get("location") or {}
        location = ", ".join(loc.get("area") or []) if isinstance(loc, dict) else str(loc)
        # Adzuna fills salary_min/max with its own model estimate when the advert has none
        # (salary_is_predicted == "1"). Estimates are never salary evidence here.
        predicted = str(payload.get("salary_is_predicted", "0")) == "1"
        salary_min = None if predicted else payload.get("salary_min")
        salary_max = None if predicted else payload.get("salary_max")
        has_salary = salary_min is not None or salary_max is not None
        return RawJobRecord(
            source_name=self.source_name,
            source_type=self.source_type,
            source_job_id=str(payload.get("id") or payload.get("redirect_url")),
            source_url=payload.get("redirect_url") or "",
            title=str(payload.get("title") or ""),
            company=(payload.get("company") or {}).get("display_name") if isinstance(payload.get("company"), dict) else payload.get("company"),
            description_html=payload.get("description"),
            description_text=strip_html(payload.get("description")),
            location_text=location or None,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=_currency_for_country(payload.get("_country")) if has_salary else None,
            salary_period="annual" if has_salary else None,
            date_posted=parse_datetime(payload.get("created")),
            apply_url=payload.get("redirect_url"),
            raw_payload={"country": payload.get("_country"), "salary_predicted": predicted},
            source_preference=SourcePreference.AGGREGATOR,
        )
