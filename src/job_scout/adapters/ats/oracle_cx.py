"""Oracle Recruiting Cloud (Candidate Experience) career sites via their public REST JSON.

These are the endpoints the public career site calls from the browser:

    GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true&finder=findReqs;siteNumber={site},keyword={term},limit=25,offset=0
    GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
        ?onlyData=true&expand=all&finder=ById;Id="{id}",siteNumber={site}

The list has no description, so details are fetched only for titles that pass the
job-family filter. Verified on GHD (2026-11-19).
"""

from __future__ import annotations

import logging
from typing import Any, Iterable
from urllib.parse import quote

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.utils.dates import parse_datetime
from job_scout.utils.text import strip_html

logger = logging.getLogger(__name__)


def _title_filter():
    from job_scout.config.settings import load_profile
    from job_scout.pipelines.common import is_family_relevant

    try:
        profile = load_profile()
    except Exception:  # noqa: BLE001
        return lambda _title: True
    return lambda title: is_family_relevant(title, "", profile)


class OracleCxAdapter(SourceAdapter):
    source_name = "oracle_cx"
    source_type = SourceType.ATS
    supported_regions = ("global",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient()
        delay = float(self.config.get("request_delay_seconds", 1.0))
        page = int(self.config.get("page_size", 25))
        max_pages = int(self.config.get("max_pages", 2))
        title_ok = _title_filter()
        try:
            for emp in self.config.get("employers") or []:
                if emp.get("enabled") is False or not emp.get("host") or not emp.get("site"):
                    continue
                base = f"https://{emp['host']}/hcmRestApi/resources/latest"
                countries = {c.upper() for c in emp.get("countries") or []}
                limit = int(emp.get("max_jobs", 60))
                emitted = 0
                seen: set[str] = set()
                for term in emp.get("searches") or self.config.get("searches") or ["engineer"]:
                    for p in range(max_pages):
                        if emitted >= limit:
                            break
                        # Oracle rejects a URL-encoded finder (";", "=", ","), so build it verbatim.
                        finder = (
                            f"findReqs;siteNumber={emp['site']},keyword={quote(str(term))},"
                            f"limit={page},offset={p * page},sortBy=POSTING_DATES_DESC"
                        )
                        try:
                            data = client.get_json(
                                f"{base}/recruitingCEJobRequisitions?onlyData=true"
                                f"&expand=requisitionList.secondaryLocations&finder={finder}",
                                delay=delay,
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Oracle CX list failed %s: %s", emp["host"], type(exc).__name__)
                            break
                        reqs = ((data.get("items") or [{}])[0] or {}).get("requisitionList") or []
                        for req in reqs:
                            rid = str(req.get("Id") or "")
                            if not rid or rid in seen or emitted >= limit:
                                continue
                            seen.add(rid)
                            if countries and str(req.get("PrimaryLocationCountry") or "").upper() not in countries:
                                continue
                            if not title_ok(str(req.get("Title") or "")):
                                continue
                            detail: dict[str, Any] = {}
                            try:
                                d = client.get_json(
                                    f"{base}/recruitingCEJobRequisitionDetails?onlyData=true&expand=all"
                                    f'&finder=ById;Id=%22{rid}%22,siteNumber={emp["site"]}',
                                    delay=delay,
                                )
                                detail = (d.get("items") or [{}])[0] or {}
                            except Exception as exc:  # noqa: BLE001
                                logger.warning("Oracle CX detail failed %s %s: %s", emp["host"], rid, type(exc).__name__)
                            payload = {**req, **detail, "_emp": emp}
                            try:
                                yield self.parse_job(payload)
                                emitted += 1
                            except Exception:  # noqa: BLE001
                                continue
                        if len(reqs) < page:
                            break
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        emp = payload["_emp"]
        rid = str(payload.get("Id"))
        url = f"https://{emp['host']}/hcmUI/CandidateExperience/en/sites/{emp['site']}/job/{rid}"
        html = "\n".join(
            str(payload.get(k) or "")
            for k in ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")
        )
        workplace = str(payload.get("WorkplaceTypeCode") or payload.get("WorkplaceType") or "").lower()
        hint = "remote" if "remote" in workplace else "hybrid" if "hybrid" in workplace else "onsite" if "site" in workplace else None
        return RawJobRecord(
            source_name=f"oracle_cx:{emp.get('slug') or emp['site']}",
            source_type=self.source_type,
            source_job_id=rid,
            source_url=url,
            title=str(payload.get("Title") or ""),
            company=emp.get("name"),
            description_html=html,
            description_text=strip_html(html),
            location_text=payload.get("PrimaryLocation"),
            work_mode_hint=hint,
            date_posted=parse_datetime(payload.get("PostedDate")),
            apply_url=url,
            direct_employer_url=url,
            raw_payload={"country_code": payload.get("PrimaryLocationCountry")},
            source_preference=SourcePreference.EMPLOYER_ATS,
        )
