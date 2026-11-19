"""Association career centres built on YM Careers (Community Brands) via their RSS feed.

    GET https://{host}/jobs/?display=rss&keywords=<term>

Item titles are "Job title | Employer" and descriptions start with "City, State, ...".
NSPE (National Society of Professional Engineers) answers; AWWA, ASCE, ASQ, ASME and ASHRAE
career centres return 403 to automated clients and are deliberately not used.
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

_LEADING_LOCATION = re.compile(r"^\s*([A-Z][A-Za-z .'-]+,\s*[A-Za-z .'-]+?)\s*,\s+")


def split_title_company(raw: str) -> tuple[str, str | None]:
    if " | " in raw:
        title, company = raw.rsplit(" | ", 1)
        return title.strip(), company.strip() or None
    return raw.strip(), None


class YmCareersAdapter(SourceAdapter):
    source_name = "ym_careers"
    source_type = SourceType.RSS
    supported_regions = ("US",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient()
        delay = float(self.config.get("request_delay_seconds", 1.0))
        try:
            for board in self.config.get("boards") or []:
                if board.get("enabled") is False or not board.get("host"):
                    continue
                seen: set[str] = set()
                for term in board.get("searches") or self.config.get("searches") or ["engineer"]:
                    url = f"https://{board['host']}/jobs/"
                    try:
                        entries = client.get_rss(url, params={"display": "rss", "keywords": term}, delay=delay)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("YM Careers RSS failed %s: %s", board["host"], type(exc).__name__)
                        break
                    for entry in entries:
                        link = str(entry.get("link") or "")
                        if not link or link in seen:
                            continue
                        seen.add(link)
                        entry["_board"] = board.get("slug") or board["host"]
                        try:
                            yield self.parse_job(entry)
                        except Exception:  # noqa: BLE001
                            continue
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        title, company = split_title_company(strip_html(str(payload.get("title") or "")))
        text = strip_html(payload.get("summary") or payload.get("description") or "")
        loc_match = _LEADING_LOCATION.match(text)
        link = str(payload.get("link") or "")
        job_id = re.search(r"/jobs/(?:rss/)?(\d+)", link)
        return RawJobRecord(
            source_name=f"ym:{payload.get('_board')}",
            source_type=self.source_type,
            source_job_id=job_id.group(1) if job_id else link,
            source_url=link,
            title=title,
            company=company,
            description_html=payload.get("summary") or payload.get("description"),
            description_text=text,
            location_text=loc_match.group(1) if loc_match else None,
            date_posted=parse_datetime(payload.get("published") or payload.get("updated")),
            apply_url=link,
            source_preference=SourcePreference.SPECIALIST_BOARD,
        )
