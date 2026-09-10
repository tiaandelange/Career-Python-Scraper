"""DWS (Department of Water and Sanitation) HTML vacancy bulletins + per-post PDFs."""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable
from urllib.parse import urljoin

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.services.dpsa_pdf import (
    is_engineering_relevant,
    parse_single_osd_advert,
    pdf_bytes_to_text,
)
from job_scout.utils.dates import parse_datetime, utcnow

logger = logging.getLogger(__name__)

INDEX_URL = "https://www.dws.gov.za/vacancies/default.aspx"
BASE = "https://www.dws.gov.za"
APPLY_PORTAL = "https://erecruitment.dws.gov.za"

_BULLETIN_HREF = re.compile(r"vacancies/current/[^\"']+\.aspx", re.I)
_REF_CELL = re.compile(r"^[A-Z0-9][A-Z0-9/_-]{2,}$", re.I)


class DwsVacanciesAdapter(SourceAdapter):
    """DWS dated bulletin pages (e.g. 11Sept2026.aspx) with PDF adverts per post."""

    source_name = "dws_vacancies"
    source_type = SourceType.HTML
    supported_regions = ("ZA",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        client = HttpClient(
            allowed_hosts={"www.dws.gov.za", "dws.gov.za"},
            max_bytes=20 * 1024 * 1024,
        )
        max_bulletins = int(self.config.get("max_bulletins", 3))
        max_jobs = int(self.config.get("max_jobs_per_source", 250))
        yielded = 0
        seen: set[str] = set()
        try:
            for bulletin_url in self._latest_bulletin_urls(client, limit=max_bulletins):
                for row in self._parse_bulletin_rows(client, bulletin_url):
                    if yielded >= max_jobs:
                        return
                    ref = row["ref"]
                    title = row["title"]
                    if ref in seen:
                        continue
                    if not is_engineering_relevant(title, title):
                        continue
                    seen.add(ref)
                    body = ""
                    salary_text = None
                    centre = None
                    pdf_url = row.get("pdf_url") or ""
                    if pdf_url:
                        try:
                            data = client.get_bytes(
                                pdf_url,
                                delay=self.config.get("request_delay_seconds", 1.0),
                            )
                            body = pdf_bytes_to_text(data)
                            parsed = parse_single_osd_advert(
                                body,
                                post_id=ref,
                                title_hint=title,
                                source_pdf_url=pdf_url,
                                department_hint="Department of Water and Sanitation",
                            )
                            if parsed:
                                salary_text = parsed.salary_text
                                centre = parsed.centre
                                body = parsed.body
                                if parsed.closing_date:
                                    row["closing_date"] = parsed.closing_date
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("DWS PDF failed %s: %s", pdf_url, exc)
                    yield self._to_raw(row, bulletin_url, salary_text, centre, body, pdf_url)
                    yielded += 1
        finally:
            client.close()

    def _latest_bulletin_urls(self, client: HttpClient, *, limit: int) -> list[str]:
        soup = client.get_soup(INDEX_URL, delay=self.config.get("request_delay_seconds", 1.0))
        urls: list[str] = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).replace("\\", "/")
            text = a.get_text(" ", strip=True)
            if _BULLETIN_HREF.search(href) or (
                "closing date" in text.lower() and href.lower().endswith(".aspx")
            ):
                full = urljoin(INDEX_URL, href)
                if full not in urls:
                    urls.append(full)
            if len(urls) >= limit:
                break
        return urls

    def _parse_bulletin_rows(self, client: HttpClient, bulletin_url: str) -> list[dict[str, Any]]:
        soup = client.get_soup(bulletin_url, delay=self.config.get("request_delay_seconds", 1.0))
        rows: list[dict[str, Any]] = []
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue
            ref = cells[0].get_text(" ", strip=True)
            title_cell = cells[1]
            title = title_cell.get_text(" ", strip=True)
            closing_raw = cells[2].get_text(" ", strip=True)
            if not ref or not title or not _REF_CELL.match(ref):
                continue
            if ref.lower() in {"reference no.", "reference no", "ref"}:
                continue
            pdf_url = ""
            link = title_cell.find("a", href=True)
            if link and str(link["href"]).lower().endswith(".pdf"):
                pdf_url = urljoin(bulletin_url, str(link["href"]))
            closing = None
            # "11 September 2026 Time: 16H00"
            date_part = re.split(r"\bTime\b", closing_raw, maxsplit=1, flags=re.I)[0].strip()
            dt = parse_datetime(date_part)
            if dt:
                closing = dt.date()
            rows.append(
                {
                    "ref": ref.replace("\\", "/"),
                    "title": title,
                    "closing_date": closing,
                    "pdf_url": pdf_url,
                }
            )
        return rows

    def _to_raw(
        self,
        row: dict[str, Any],
        bulletin_url: str,
        salary_text: str | None,
        centre: str | None,
        body: str,
        pdf_url: str,
    ) -> RawJobRecord:
        ref = str(row["ref"])
        location = f"{centre}, South Africa" if centre else "South Africa"
        apply_url = APPLY_PORTAL
        source_url = pdf_url or f"{bulletin_url}#{ref}"
        return RawJobRecord(
            source_name=self.source_name,
            source_type=self.source_type,
            source_job_id=ref,
            source_url=source_url,
            title=str(row["title"]),
            company="Department of Water and Sanitation",
            description_text=body or str(row["title"]),
            description_html=None,
            location_text=location,
            work_mode_hint="onsite",
            salary_text=salary_text,
            salary_currency="ZAR" if salary_text else None,
            salary_period="annual" if salary_text else None,
            closing_date=row.get("closing_date"),
            date_posted=utcnow(),
            apply_url=apply_url,
            direct_employer_url=apply_url,
            raw_payload={
                "bulletin": bulletin_url,
                "pdf": pdf_url or None,
                "ref": ref,
            },
            source_preference=SourcePreference.GOVERNMENT,
        )
