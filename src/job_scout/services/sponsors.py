"""US green-card sponsor history from the Department of Labor's PERM disclosure data.

An employer that recently got PERM labor certifications for engineers is the strongest
public signal that it will sponsor an EB-2 / EB-3 green card - far more reliable than
whether one advert happens to mention visas.

Build the list (once per year, after downloading the xlsx from
https://www.dol.gov/agencies/eta/foreign-labor/performance in a browser):

    pip install -e ".[data]"
    python -m job_scout sponsors path/to/PERM_Disclosure_Data_FY2025.xlsx [more.xlsx ...]

which writes config/visa_sponsors.csv. Without that file every lookup returns None.
"""

from __future__ import annotations

import csv
import logging
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from job_scout.config.settings import get_settings
from job_scout.utils.text import normalise_key

logger = logging.getLogger(__name__)

SPONSORS_FILE = "visa_sponsors.csv"

# SOC codes for the occupations this candidate targets (engineers, engineering managers,
# engineering technologists).
ENGINEERING_SOC_PREFIXES = (
    "17-2",  # engineers (mechanical 17-2141, civil 17-2051, environmental 17-2081, ...)
    "17-3",  # engineering technologists / technicians
    "11-9041",  # architectural and engineering managers
    "11-3051",  # industrial production managers
    "11-9021",  # construction managers
)

_SUFFIXES = {
    "inc", "incorporated", "llc", "l l c", "ltd", "limited", "corp", "corporation", "co", "company",
    "lp", "llp", "plc", "pc", "pllc", "the", "holdings", "group", "usa", "us", "na", "north america",
    "americas", "technologies", "technology",
}


def employer_key(name: str | None) -> str:
    """Normalise an employer name so 'Black & Veatch Corporation' == 'Black and Veatch'."""
    text = normalise_key((name or "").replace("&", " and "))
    words = text.split()
    while words and words[0] == "the":
        words = words[1:]
    changed = True
    while changed and words:
        changed = False
        for size in (3, 2, 1):
            if len(words) > size and " ".join(words[-size:]) in _SUFFIXES:
                words = words[:-size]
                changed = True
                break
    return " ".join(words)


@dataclass(frozen=True)
class SponsorRecord:
    employer: str
    engineering_certified: int
    total_certified: int


@lru_cache(maxsize=1)
def _load() -> dict[str, SponsorRecord]:
    path = get_settings().config_dir() / SPONSORS_FILE
    if not path.exists():
        return {}
    out: dict[str, SponsorRecord] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                rec = SponsorRecord(
                    employer=row["employer"],
                    engineering_certified=int(row["engineering_certified"]),
                    total_certified=int(row["total_certified"]),
                )
            except (KeyError, ValueError):
                continue
            out[row["employer_key"]] = rec
    logger.info("Loaded %s PERM sponsor employers", len(out))
    return out


def clear_cache() -> None:
    _load.cache_clear()


def lookup(company: str | None) -> SponsorRecord | None:
    key = employer_key(company)
    if not key:
        return None
    sponsors = _load()
    if not sponsors:
        return None
    if key in sponsors:
        return sponsors[key]
    # "Black & Veatch Holding Company" -> "black and veatch holding": try shorter prefixes,
    # but never below two words, so "Water" can never match "Water Corp".
    words = key.split()
    for size in range(len(words) - 1, 1, -1):
        hit = sponsors.get(" ".join(words[:size]))
        if hit:
            return hit
    return None


# --- building the CSV from DOL xlsx files ---------------------------------------------


def _find_col(headers: list[str], *needles: str, exclude: tuple[str, ...] = ()) -> int | None:
    for idx, header in enumerate(headers):
        h = (header or "").upper()
        if all(n in h for n in needles) and not any(x in h for x in exclude):
            return idx
    return None


def build_sponsor_csv(xlsx_paths: list[Path], out_path: Path) -> dict[str, int]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError('openpyxl is required: pip install -e ".[data]"') from exc

    names: dict[str, Counter] = {}
    eng: Counter = Counter()
    total: Counter = Counter()
    rows_read = 0
    for path in xlsx_paths:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        headers = [str(h or "") for h in next(rows)]
        # Old and revised ETA-9089 files name these columns differently; match loosely.
        status_col = _find_col(headers, "CASE_STATUS")
        employer_col = None
        for candidate in (
            _find_col(headers, "EMPLOYER", "NAME", exclude=("CONTACT", "POC", "FIRST", "LAST", "PREPARER")),
            _find_col(headers, "EMP_BUSINESS_NAME"),
            _find_col(headers, "BUSINESS_NAME", exclude=("AGENT", "ATTY", "LAWFIRM")),
        ):
            if candidate is not None:  # column 0 is a valid index
                employer_col = candidate
                break
        soc_col = _find_col(headers, "SOC_CODE", exclude=("TITLE",))
        if status_col is None or employer_col is None or soc_col is None:
            raise RuntimeError(
                f"{path.name}: could not find CASE_STATUS / employer name / SOC code columns "
                f"(found {len(headers)} columns)"
            )
        for row in rows:
            rows_read += 1
            status = str(row[status_col] or "").lower()
            if not status.startswith("certified"):
                continue
            employer = str(row[employer_col] or "").strip()
            key = employer_key(employer)
            if not key:
                continue
            names.setdefault(key, Counter())[employer] += 1
            total[key] += 1
            soc = str(row[soc_col] or "").strip()
            if soc.startswith(ENGINEERING_SOC_PREFIXES):
                eng[key] += 1
        wb.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["employer_key", "employer", "engineering_certified", "total_certified"])
        for key, count in sorted(eng.items(), key=lambda kv: (-kv[1], kv[0])):
            writer.writerow([key, names[key].most_common(1)[0][0], count, total[key]])
            kept += 1
    clear_cache()
    return {"rows_read": rows_read, "employers_certified": len(total), "engineering_sponsors": kept}
