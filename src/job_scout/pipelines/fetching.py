"""Fetch every enabled source once per run, in parallel, each under its own time budget.

Before this existed each pipeline (remote, hybrid, on-site) re-fetched the same multi-pipeline
sources sequentially, so a run did ~3x the HTTP work and blew through the 25-minute
GitHub Actions timeout.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Iterable

from job_scout.adapters.base import SourceAdapter
from job_scout.adapters.http import FETCH_DEADLINE
from job_scout.models.job import RawJobRecord

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    jobs: list[RawJobRecord] = field(default_factory=list)
    error: Exception | None = None
    seconds: float = 0.0
    budget_hit: bool = False


def adapter_key(adapter: SourceAdapter) -> str:
    return str(adapter.config.get("name") or adapter.source_name)


def _fetch_one(adapter: SourceAdapter, budget_seconds: float) -> FetchResult:
    deadline = time.monotonic() + budget_seconds
    token = FETCH_DEADLINE.set(deadline)
    t0 = time.perf_counter()
    jobs: list[RawJobRecord] = []
    try:
        for raw in adapter.fetch_jobs():
            jobs.append(raw)
            if time.monotonic() >= deadline:
                break
        return FetchResult(
            jobs=jobs,
            seconds=round(time.perf_counter() - t0, 2),
            budget_hit=time.monotonic() >= deadline,
        )
    except Exception as exc:  # noqa: BLE001
        # Keep whatever arrived before the failure if anything did.
        if jobs:
            return FetchResult(jobs=jobs, seconds=round(time.perf_counter() - t0, 2), budget_hit=True)
        return FetchResult(error=exc, seconds=round(time.perf_counter() - t0, 2))
    finally:
        FETCH_DEADLINE.reset(token)


def prefetch_sources(
    adapters: Iterable[SourceAdapter],
    *,
    budget_seconds: float,
    workers: int,
) -> dict[str, FetchResult]:
    unique: dict[str, SourceAdapter] = {}
    for adapter in adapters:
        unique.setdefault(adapter_key(adapter), adapter)
    if not unique:
        return {}
    results: dict[str, FetchResult] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="fetch") as pool:
        futures = {name: pool.submit(_fetch_one, adapter, budget_seconds) for name, adapter in unique.items()}
        for name, future in futures.items():
            results[name] = future.result()
    for name, result in sorted(results.items(), key=lambda item: -item[1].seconds):
        logger.info(
            "fetch %-22s %6.1fs %4d jobs%s%s",
            name,
            result.seconds,
            len(result.jobs),
            " (budget hit)" if result.budget_hit else "",
            f" ERROR {type(result.error).__name__}" if result.error else "",
        )
    return results
