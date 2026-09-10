"""Generic SA public-entity careers page that links to vacancy PDFs."""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import HttpClient
from job_scout.models.enums import SourcePreference, SourceType
from job_scout.models.job import RawJobRecord
from job_scout.services.dpsa_pdf import (
    is_engineering_relevant,
    parse_circular_text,
    parse_single_osd_advert,
    pdf_bytes_to_text,
)
from job_scout.utils.dates import utcnow
from job_scout.utils.text import sha256_text

logger = logging.getLogger(__name__)

_SKIP_TITLE = re.compile(
    r"\b(bursar(?:y|ies)?|internship|learnership|graduate\s+programme|academic\s+year)\b",
    re.I,
)


class SaPdfBoardAdapter(SourceAdapter):
    """Scrape one or more HTML indexes for vacancy PDF links (water boards, SOEs)."""

    source_name = "sa_pdf_boards"
    source_type = SourceType.HTML
    supported_regions = ("ZA",)

    def fetch_jobs(self) -> Iterable[RawJobRecord]:
        boards = self.config.get("boards") or []
        max_jobs = int(self.config.get("max_jobs_per_source", 200))
        max_pdfs_per_board = int(self.config.get("max_pdfs_per_board", 12))
        yielded = 0
        seen: set[str] = set()
        for board in boards:
            if board.get("enabled") is False:
                continue
            if yielded >= max_jobs:
                break
            index_url = board.get("index_url")
            company = board.get("name") or board.get("company") or "SA public entity"
            if not index_url:
                continue
            hosts = set(board.get("hosts") or [])
            host = urlparse(index_url).hostname
            if host:
                hosts.add(host)
                if host.startswith("www."):
                    hosts.add(host[4:])
                else:
                    hosts.add(f"www.{host}")
            client = HttpClient(allowed_hosts=hosts or None, max_bytes=20 * 1024 * 1024)
            try:
                soup = client.get_soup(index_url, delay=self.config.get("request_delay_seconds", 1.0))
                pdfs = self._collect_pdfs(soup, index_url, limit=max_pdfs_per_board)
                for title_hint, pdf_url in pdfs:
                    if yielded >= max_jobs:
                        break
                    if pdf_url in seen:
                        continue
                    seen.add(pdf_url)
                    if _SKIP_TITLE.search(title_hint) or _SKIP_TITLE.search(pdf_url):
                        continue
                    try:
                        text = pdf_bytes_to_text(
                            client.get_bytes(
                                pdf_url,
                                delay=self.config.get("request_delay_seconds", 1.0),
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("PDF board fetch failed %s: %s", pdf_url, exc)
                        continue
                    posts = parse_circular_text(
                        text,
                        source_pdf_url=pdf_url,
                        department_hint=company,
                    )
                    if not posts:
                        single = parse_single_osd_advert(
                            text,
                            post_id=sha256_text(pdf_url)[:12],
                            title_hint=title_hint if title_hint.lower() not in {"download file", "pdf"} else None,
                            source_pdf_url=pdf_url,
                            department_hint=company,
                        )
                        posts = [single] if single else []
                    if not posts and is_engineering_relevant(title_hint, text):
                        # Title/filename relevant but non-OSD layout — keep with raw text for salary parse later.
                        from job_scout.services.dpsa_pdf import DpsaPost

                        salary_m = re.search(r"SALARY\s*:?\s*([^\n]+)", text, re.I)
                        centre_m = re.search(r"CENTRE\s*:?\s*([^\n]+)", text, re.I)
                        posts = [
                            DpsaPost(
                                post_id=sha256_text(pdf_url)[:12],
                                title=title_hint or "Vacancy",
                                ref_no=None,
                                salary_text=(salary_m.group(1).strip() if salary_m else None),
                                centre=(centre_m.group(1).strip() if centre_m else None),
                                closing_date=None,
                                body=text[:4000],
                                source_pdf_url=pdf_url,
                                department_hint=company,
                            )
                        ]
                    for post in posts:
                        key = f"{pdf_url}#{post.post_id}"
                        if key in seen:
                            continue
                        seen.add(key)
                        yield self._to_raw(post, company, pdf_url, board)
                        yielded += 1
                        if yielded >= max_jobs:
                            break
            except Exception as exc:  # noqa: BLE001
                logger.warning("PDF board index failed %s: %s", index_url, exc)
            finally:
                client.close()

    def _collect_pdfs(self, soup: Any, index_url: str, *, limit: int) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if not href.lower().endswith(".pdf"):
                continue
            title = a.get_text(" ", strip=True) or href.rsplit("/", 1)[-1]
            # Prefer nearby heading text when link says "Download File"
            if title.lower() in {"download file", "pdf", "click here"}:
                parent = a.find_parent(["tr", "li", "div", "td", "article"])
                if parent:
                    nearby = parent.get_text(" ", strip=True)
                    nearby = re.sub(r"download file", "", nearby, flags=re.I).strip(" -|:")
                    if nearby:
                        title = nearby[:120]
            if not title or title.lower() in {"download file", "pdf"}:
                title = href.rsplit("/", 1)[-1].replace("_", " ").replace("%20", " ")
                title = re.sub(r"\.pdf$", "", title, flags=re.I)
            full = urljoin(index_url, href)
            if full not in {u for _, u in out}:
                out.append((title, full))
            if len(out) >= limit:
                break
        return out

    def _to_raw(self, post: Any, company: str, pdf_url: str, board: dict[str, Any]) -> RawJobRecord:
        apply = board.get("apply_url") or pdf_url
        location = f"{post.centre}, South Africa" if post.centre else "South Africa"
        return RawJobRecord(
            source_name=f"{self.source_name}:{board.get('slug') or company}",
            source_type=self.source_type,
            source_job_id=str(post.post_id),
            source_url=pdf_url,
            title=post.title,
            company=company,
            description_text=post.body,
            location_text=location,
            work_mode_hint="onsite",
            salary_text=post.salary_text,
            salary_currency="ZAR" if post.salary_text else None,
            salary_period="annual" if post.salary_text else None,
            closing_date=post.closing_date,
            date_posted=utcnow(),
            apply_url=apply,
            direct_employer_url=apply,
            raw_payload={"board": board.get("slug"), "pdf": pdf_url, "index": board.get("index_url")},
            source_preference=SourcePreference.GOVERNMENT,
        )
