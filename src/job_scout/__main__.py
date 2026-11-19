"""python -m job_scout scrape|digest|health"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="job-scout")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scrape", help="Run enabled job pipelines")
    sub.add_parser("digest", help="Build and optionally send the morning digest")
    sub.add_parser("health", help="Supabase / schema health check")
    sub.add_parser("prune", help="Delete saved jobs whose links have closed")
    sub.add_parser("dashboard", help="Build the static jobs dashboard site")
    sub.add_parser("sponsors", help="Build config/visa_sponsors.csv from DOL PERM xlsx files")
    args, rest = parser.parse_known_args(argv)

    if args.command == "sponsors":
        from job_scout.orchestration.maintain import sponsors_main

        return sponsors_main(rest)

    if args.command == "prune":
        from job_scout.orchestration.maintain import prune_main

        return prune_main(rest)
    if args.command == "dashboard":
        from job_scout.orchestration.maintain import dashboard_main

        return dashboard_main(rest)

    if args.command == "scrape":
        from job_scout.orchestration.run_scrapers import main as scrape_main

        return scrape_main(rest)
    if args.command == "digest":
        from job_scout.orchestration.send_digest import main as digest_main

        return digest_main(rest)
    from job_scout.orchestration.health_check import main as health_main

    return health_main(rest)


if __name__ == "__main__":
    sys.exit(main())
