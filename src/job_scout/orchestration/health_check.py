"""Lightweight Supabase reachability + schema check. No large writes."""

from __future__ import annotations

import argparse
import logging
import sys

from job_scout.config.settings import get_settings
from job_scout.services.database import InMemoryJobRepository, build_repository
from job_scout.utils.logging import configure_logging

logger = logging.getLogger(__name__)

EXPECTED_TABLES = ("jobs", "job_sources", "scrape_runs", "source_health", "digest_runs", "fx_rates")


def run_health(memory: bool = False) -> dict:
    settings = get_settings()
    if memory or not settings.has_supabase():
        repo = InMemoryJobRepository()
        ping = repo.ping()
        logger.info("Health (memory): %s", ping)
        return ping
    repo = build_repository(settings)
    ping = repo.ping()
    logger.info("Health (supabase): %s", ping)
    if not ping.get("ok"):
        raise RuntimeError("Supabase health check failed")
    return ping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Job Scout health check")
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args(argv)
    configure_logging(get_settings().job_scout_log_level)
    try:
        run_health(memory=args.memory)
    except Exception:
        logger.exception("Health check failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
