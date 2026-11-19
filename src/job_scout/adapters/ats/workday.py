"""Workday career sites via the public candidate-experience (cxs) JSON endpoints.

These are the same unauthenticated endpoints the public career site calls from the browser:

    POST https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    GET  https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{externalPath}

Workday rate-limits per IP, so each employer is searched with a few targeted keywords, titles
are pre-filtered against the job families before any detail call, and requests are spaced out.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.utils.dates import parse_datetime
from job_scout.utils.text import strip_html

logger = logging.getLogger(__name__)

DEFAULT_SEARCHES = ["mechanical engineer", "project engineer", "water", "project manager"]


def _title_filter():
    from job_scout.config.settings import load_profile
    from job_scout.pipelines.common import is_family_relevant

    try:
        profile = load_profile()
    except Exception:  # noqa: BLE001
        return lambda _title: True
    return lambda title: is_family_relevant(title, "", profile)


class WorkdayAdapter(SourceAdapter):
    source_name = "workday"
    source_type = SourceType.ATS
    supported_regions = ("US", "global")

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient()
        delay = float(self.config.get("request_delay_seconds", 1.5))
        page_size = 20
        max_pages = int(self.config.get("max_pages", 2))
        max_per_employer = int(self.config.get("max_jobs_per_employer", 40))
        title_ok = _title_filter()
        try:
            for employer in self.config.get("employers") or []:
                if employer.get("enabled") is False:
                    continue
                tenant, pod, site = employer.get("tenant"), employer.get("pod"), employer.get("site")
                if not (tenant and pod and site):
                    continue
                base = f"https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
                public_base = f"https://{tenant}.{pod}.myworkdayjobs.com/en-US/{site}"
                seen_paths: set[str] = set()
                emitted = 0
                searches = employer.get("searches") or self.config.get("searches") or DEFAULT_SEARCHES
                blocked = False
                for text in searches:
                    if emitted >= max_per_employer or blocked:
                        break
                    for page in range(max_pages):
                        try:
                            payload = client.post_json(
                                f"{base}/jobs",
                                {"appliedFacets": {}, "limit": page_size, "offset": page * page_size, "searchText": text},
                                delay=delay,
                            )
                        except Exception as exc:  # noqa: BLE001
                            # Usually 429 or a renamed site: skip this employer's other searches too.
                            logger.warning("Workday list failed %s/%s: %s", tenant, site, type(exc).__name__)
                            blocked = True
                            break
                        postings = payload.get("jobPostings") or []
                        for post in postings:
                            path = post.get("externalPath")
                            title = str(post.get("title") or "")
                            if not path or path in seen_paths or not title_ok(title):
                                continue
                            seen_paths.add(path)
                            if emitted >= max_per_employer:
                                break
                            try:
                                detail = client.get_json(f"{base}{path}", delay=delay)
                            except Exception as exc:  # noqa: BLE001
                                logger.warning("Workday detail failed %s: %s", tenant, type(exc).__name__)
                                continue
                            info = (detail or {}).get("jobPostingInfo") or {}
                            info["_company"] = employer.get("name") or tenant
                            info["_tenant"] = tenant
                            info["_public_url"] = info.get("externalUrl") or f"{public_base}{path}"
                            info["_list_location"] = post.get("locationsText")
                            try:
                                yield self.parse_job(info)
                                emitted += 1
                            except Exception:  # noqa: BLE001
                                continue
                        if len(postings) < page_size:
                            break
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        location = payload.get("location") or payload.get("_list_location") or ""
        country = (payload.get("country") or {}).get("descriptor") if isinstance(payload.get("country"), dict) else None
        if country and country.lower() not in location.lower():
            location = f"{location}, {country}" if location else country
        remote_type = str(payload.get("remoteType") or "").lower()
        hint = None
        if "remote" in remote_type:
            hint = "remote"
        elif "hybrid" in remote_type:
            hint = "hybrid"
        elif remote_type:
            hint = "onsite"
        url = payload["_public_url"]
        description = payload.get("jobDescription")
        return RawJobRecord(
            source_name=f"workday:{payload.get('_tenant')}",
            source_type=self.source_type,
            source_job_id=str(payload.get("jobReqId") or payload.get("id") or url),
            source_url=url,
            title=str(payload.get("title") or ""),
            company=payload.get("_company"),
            description_html=description,
            description_text=strip_html(description),
            location_text=location or None,
            work_mode_hint=hint,
            date_posted=parse_datetime(payload.get("startDate") or payload.get("postedOn")),
            apply_url=url,
            direct_employer_url=url,
            raw_payload={"time_type": payload.get("timeType"), "remote_type": payload.get("remoteType")},
            source_preference=SourcePreference.EMPLOYER_ATS,
        )
