"""DPWI (Public Works & Infrastructure) vacancy PDF index."""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.services.dpsa_pdf import DpsaPost, parse_circular_text, pdf_bytes_to_text
from job_scout.utils.dates import utcnow

logger = logging.getLogger(__name__)

INDEX_URL = "http://www.publicworks.gov.za/vacancies.html"
BASE = "http://www.publicworks.gov.za"


class DpwiVacanciesAdapter(SourceAdapter):
    """DPWI vacancies.html lists DPSA-format PDF adverts with engineering posts."""

    source_name = "dpwi_vacancies"
    source_type = SourceType.HTML
    supported_regions = ("ZA",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient(
            allowed_hosts={"www.publicworks.gov.za", "publicworks.gov.za"},
            max_bytes=20 * 1024 * 1024,
        )
        max_pdfs = int(self.config.get("max_pdfs", 3))
        max_jobs = int(self.config.get("max_jobs_per_source", 250))
        yielded = 0
        seen: set[str] = set()
        try:
            for pdf_url, label in self._latest_pdfs(client, limit=max_pdfs):
                if yielded >= max_jobs:
                    return
                try:
                    data = client.get_bytes(
                        pdf_url,
                        delay=self.config.get("request_delay_seconds", 1.0),
                    )
                    text = pdf_bytes_to_text(data)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("DPWI PDF failed %s: %s", pdf_url, exc)
                    continue
                for post in parse_circular_text(
                    text,
                    source_pdf_url=pdf_url,
                    department_hint=label or "Department of Public Works and Infrastructure",
                ):
                    key = f"{pdf_url}#{post.post_id}"
                    if key in seen:
                        continue
                    seen.add(key)
                    yield self._to_raw(post, pdf_url)
                    yielded += 1
                    if yielded >= max_jobs:
                        return
        finally:
            client.close()

    def _latest_pdfs(self, client: HttpClient, *, limit: int) -> list[tuple[str, str]]:
        soup = client.get_soup(INDEX_URL, delay=self.config.get("request_delay_seconds", 1.0))
        candidates: list[tuple[int, str, str]] = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            label = a.get_text(" ", strip=True)
            if not href.lower().endswith(".pdf"):
                continue
            href_l = href.lower()
            label_l = label.lower()
            if "2026vacancies" not in href_l and "vacanc" not in href_l and "advert" not in label_l:
                continue
            # Prefer DPSA-format annexures (POST N/N); de-prioritise "External Adverts".
            rank = 0
            if "dpsa" in label_l or "dpsa" in href_l:
                rank = 0
            elif "external" in label_l:
                rank = 2
            else:
                rank = 1
            full = urljoin(BASE + "/", href)
            candidates.append((rank, full, label))
        # Stable: keep page order within the same rank.
        candidates.sort(key=lambda item: (item[0],))
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for _, full, label in candidates:
            # Skip near-duplicate ".1.pdf" twins when base PDF exists.
            if full.endswith(".1.pdf") and full[:-6] + ".pdf" in {u for u, _ in out}:
                continue
            if full in seen:
                continue
            seen.add(full)
            out.append((full, label))
            if len(out) >= limit:
                break
        return out

    def _to_raw(self, post: DpsaPost, pdf_url: str) -> RawJobRecord:
        year_match = re.search(r"(20\d{2})", pdf_url)
        year = year_match.group(1) if year_match else "unknown"
        source_job_id = f"{year}-{post.post_id}"
        post_url = f"{pdf_url}#post-{post.post_id}"
        company = post.department_hint or "Department of Public Works and Infrastructure"
        return RawJobRecord(
            source_name=self.source_name,
            source_type=self.source_type,
            source_job_id=source_job_id,
            source_url=post_url,
            title=post.title,
            company=company,
            description_text=post.body,
            location_text=(f"{post.centre}, South Africa" if post.centre else "South Africa"),
            work_mode_hint="onsite",
            salary_text=post.salary_text,
            salary_currency="ZAR" if post.salary_text else None,
            salary_period="annual" if post.salary_text else None,
            closing_date=post.closing_date,
            date_posted=utcnow(),
            apply_url=post_url,
            direct_employer_url=post_url,
            raw_payload={"pdf": pdf_url, "post_id": post.post_id, "ref_no": post.ref_no},
            source_preference=SourcePreference.GOVERNMENT,
        )
