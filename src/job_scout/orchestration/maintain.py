"""`prune` deletes closed jobs; `dashboard` writes the static GitHub Pages site."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from job_scout.config.settings import get_settings, load_scoring
from job_scout.services.database import InMemoryJobRepository, build_repository
from job_scout.utils.logging import configure_logging

logger = logging.getLogger(__name__)


def _repo(memory: bool):
    settings = get_settings()
    if not memory and settings.job_scout_env == "github" and not settings.has_supabase():
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in GitHub mode")
    return InMemoryJobRepository() if memory else build_repository(settings)


def prune_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Delete saved jobs whose postings have closed")
    parser.add_argument("--dry-run", action="store_true", help="Report closed jobs without deleting")
    parser.add_argument("--stale-days", type=int, default=7)
    parser.add_argument(
        "--no-stale",
        action="store_true",
        help="Skip the 'not seen for N days' rule (use when the scrape did not complete)",
    )
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args(argv)
    configure_logging(get_settings().job_scout_log_level)
    from job_scout.services.link_check import prune_closed_jobs

    try:
        stale_days = 0 if args.no_stale else args.stale_days
        if args.no_stale:
            logger.info("Scrape did not complete: staleness rule disabled for this prune")
        prune_closed_jobs(_repo(args.memory), dry_run=args.dry_run, stale_days=stale_days)
        return 0
    except Exception:
        logger.exception("Prune failed")
        return 1


def dashboard_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the static jobs dashboard")
    parser.add_argument("--out", default="site", help="Output directory (default: site)")
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.job_scout_log_level)
    from job_scout.services.dashboard import build_dashboard

    try:
        repo = _repo(args.memory)
        min_score = int(load_scoring(settings).get("low_score_cutoff", 60))
        from job_scout.adapters.registry import inactive_source_names

        inactive = inactive_source_names()
        health = {"sources_failed": 0, "failed_sources": []}
        for row in repo.list_source_health():
            if row.get("source") in inactive:
                continue
            if row.get("consecutive_failures", 0) > 0:
                health["sources_failed"] += 1
                health["failed_sources"].append(row.get("source"))
        stats = build_dashboard(repo.list_active_jobs(), Path(args.out), min_score=min_score, health=health)
        logger.info("Dashboard stats: %s", stats)
        return 0
    except Exception:
        logger.exception("Dashboard build failed")
        return 1


def sponsors_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the US green-card sponsor list from DOL PERM data")
    parser.add_argument("xlsx", nargs="+", type=Path, help="PERM_Disclosure_Data_*.xlsx downloaded from dol.gov")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.job_scout_log_level)
    from job_scout.services.sponsors import SPONSORS_FILE, build_sponsor_csv

    out = settings.config_dir() / SPONSORS_FILE
    try:
        stats = build_sponsor_csv(args.xlsx, out)
    except Exception:
        logger.exception("Sponsor list build failed")
        return 1
    logger.info("Wrote %s: %s", out, stats)
    return 0
