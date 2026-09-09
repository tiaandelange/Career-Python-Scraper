"""Reusable SmartRecruiters public postings API."""

from __future__ import annotations

from typing import Any, Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.utils.dates import parse_datetime
from job_scout.utils.text import strip_html


class SmartRecruitersAdapter(SourceAdapter):
    source_name = "smartrecruiters"
    source_type = SourceType.ATS

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient()
        max_pages = int(self.config.get("max_pages", 3))
        try:
            for employer in self.config.get("employers") or []:
                if employer.get("enabled") is False or not employer.get("slug"):
                    continue
                slug = employer["slug"]
                offset = 0
                for _ in range(max_pages):
                    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                    try:
                        payload = client.get_json(
                            url,
                            params={"limit": 100, "offset": offset},
                            delay=self.config.get("request_delay_seconds", 1.0),
                        )
                    except Exception:
                        break
                    jobs = payload.get("content") or payload.get("jobs") or []
                    if not jobs:
                        break
                    for item in jobs:
                        item["_company"] = employer.get("name") or slug
                        item["_slug"] = slug
                        try:
                            yield self.parse_job(item)
                        except Exception:
                            continue
                    offset += 100
                    if len(jobs) < 100:
                        break
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        loc = payload.get("location") or {}
        city = loc.get("city")
        country = loc.get("countryCode") or loc.get("country")
        location = ", ".join(p for p in [city, country] if p)
        remote = loc.get("remote") or payload.get("remote")
        return RawJobRecord(
            source_name=f"smartrecruiters:{payload.get('_slug')}",
            source_type=self.source_type,
            source_job_id=str(payload.get("id") or payload.get("uuid") or payload.get("refNumber")),
            source_url=payload.get("ref") or payload.get("applyUrl") or payload.get("id") and f"https://jobs.smartrecruiters.com/{payload.get('_slug')}/{payload.get('id')}" or "",
            title=str(payload.get("name") or payload.get("title") or ""),
            company=payload.get("_company"),
            description_html=(payload.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text")
            if isinstance(payload.get("jobAd"), dict)
            else payload.get("description"),
            description_text=strip_html(
                (payload.get("jobAd") or {}).get("sections", {}).get("jobDescription", {}).get("text")
                if isinstance(payload.get("jobAd"), dict)
                else payload.get("description")
            ),
            location_text=location or None,
            work_mode_hint="remote" if remote else None,
            date_posted=parse_datetime(payload.get("releasedDate") or payload.get("createdOn")),
            apply_url=payload.get("applyUrl") or payload.get("ref"),
            direct_employer_url=payload.get("ref"),
            raw_payload={"department": (payload.get("department") or {}).get("label") if isinstance(payload.get("department"), dict) else payload.get("department")},
            source_preference=SourcePreference.EMPLOYER_ATS,
        )
