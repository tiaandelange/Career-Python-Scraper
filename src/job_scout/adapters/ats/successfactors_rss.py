"""SAP SuccessFactors career sites (Recruiting Marketing) via their public RSS job feed.

    GET https://{host}/services/rss/job/?locale=en_US&keywords=<term>

Works on Black & Veatch, Hatch and Sasol (verified 2026-11-19). Many other SuccessFactors
sites have the feed switched off; those simply return no items and are skipped.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.utils.dates import parse_datetime
from job_scout.utils.text import strip_html

logger = logging.getLogger(__name__)

_LOCATION_SUFFIX = re.compile(r"\s*\(([^()]*)\)\s*$")


def split_title_location(raw_title: str) -> tuple[str, str | None]:
    """'Senior Piping Engineer (Brisbane, Queensland, AU)' -> ('Senior Piping Engineer', 'Brisbane, Queensland, AU')."""
    match = _LOCATION_SUFFIX.search(raw_title or "")
    if not match:
        return (raw_title or "").strip(), None
    return raw_title[: match.start()].strip(), match.group(1).strip() or None


class SuccessFactorsRssAdapter(SourceAdapter):
    source_name = "successfactors"
    source_type = SourceType.ATS
    supported_regions = ("global",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient()
        delay = float(self.config.get("request_delay_seconds", 1.0))
        try:
            for site in self.config.get("sites") or []:
                if site.get("enabled") is False or not site.get("host"):
                    continue
                seen: set[str] = set()
                for term in site.get("searches") or self.config.get("searches") or ["engineer"]:
                    url = f"https://{site['host']}/services/rss/job/"
                    try:
                        entries = client.get_rss(url, params={"locale": site.get("locale", "en_US"), "keywords": term}, delay=delay)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("SuccessFactors RSS failed %s: %s", site["host"], type(exc).__name__)
                        break
                    for entry in entries:
                        link = str(entry.get("link") or "")
                        if not link or link in seen:
                            continue
                        seen.add(link)
                        entry["_company"] = site.get("name") or site["host"]
                        entry["_slug"] = site.get("slug") or site["host"].split(".")[1]
                        try:
                            yield self.parse_job(entry)
                        except Exception:  # noqa: BLE001
                            continue
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        title, location = split_title_location(str(payload.get("title") or ""))
        link = str(payload.get("link") or "")
        html = payload.get("summary") or payload.get("description") or ""
        return RawJobRecord(
            source_name=f"successfactors:{payload.get('_slug')}",
            source_type=self.source_type,
            source_job_id=link,
            source_url=link,
            title=title,
            company=payload.get("_company"),
            description_html=html,
            description_text=strip_html(html),
            location_text=location,
            date_posted=parse_datetime(payload.get("published") or payload.get("updated")),
            apply_url=link,
            direct_employer_url=link,
            source_preference=SourcePreference.EMPLOYER_ATS,
        )
