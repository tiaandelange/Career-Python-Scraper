"""SANRAL open vacancies HTML list (nra.co.za careers portal)."""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urljoin

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.services.dpsa_pdf import is_engineering_relevant
from job_scout.utils.dates import utcnow
from job_scout.utils.text import sha256_text

INDEX_URL = "https://www.nra.co.za/sanral-careers/list/open-vacancies"
BASE = "https://www.nra.co.za"


class SanralVacanciesAdapter(SourceAdapter):
    """SANRAL careers open-vacancies table — engineering / project roles."""

    source_name = "sanral_vacancies"
    source_type = SourceType.HTML
    supported_regions = ("ZA",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient(
            allowed_hosts={"www.nra.co.za", "nra.co.za"},
            max_bytes=5 * 1024 * 1024,
        )
        max_jobs = int(self.config.get("max_jobs_per_source", 100))
        yielded = 0
        try:
            soup = client.get_soup(INDEX_URL, delay=self.config.get("request_delay_seconds", 1.0))
            for tr in soup.find_all("tr"):
                if yielded >= max_jobs:
                    break
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if len(cells) < 2:
                    continue
                title = cells[0]
                location = cells[1] if len(cells) > 1 else ""
                employment = cells[2] if len(cells) > 2 else ""
                if not title or title.lower() in {"position", "title"}:
                    continue
                if not is_engineering_relevant(title, f"{title} {location} {employment}"):
                    # Keep infrastructure PM / contract engineer style titles
                    if not re.search(r"\b(engineer|technolog|project\s+manager|contract\s+engineer)\b", title, re.I):
                        continue
                link = tr.find("a", href=True)
                detail = urljoin(BASE, str(link["href"])) if link else INDEX_URL
                yield self.parse_job(
                    {
                        "title": title,
                        "location": location,
                        "employment": employment,
                        "url": detail,
                    }
                )
                yielded += 1
        finally:
            client.close()

    def parse_job(self, payload: dict[str, Any]) -> RawJobRecord:
        title = str(payload.get("title") or "")
        url = str(payload.get("url") or INDEX_URL)
        location = str(payload.get("location") or "South Africa")
        employment = str(payload.get("employment") or "")
        return RawJobRecord(
            source_name=self.source_name,
            source_type=self.source_type,
            source_job_id=sha256_text(title, location, url)[:24],
            source_url=url,
            title=title,
            company="SANRAL",
            description_text=f"{title}. {employment}. Location: {location}. Apply via SANRAL careers portal.",
            location_text=f"{location}, South Africa" if "south africa" not in location.lower() else location,
            work_mode_hint="onsite",
            date_posted=utcnow(),
            apply_url=url if url != INDEX_URL else INDEX_URL,
            direct_employer_url=INDEX_URL,
            raw_payload={"employment": employment},
            source_preference=SourcePreference.GOVERNMENT,
        )
