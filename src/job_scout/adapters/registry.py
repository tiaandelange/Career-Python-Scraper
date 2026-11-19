"""Load enabled adapters from sources.yaml without importing Playwright."""

from __future__ import annotations

import importlib
import logging
from typing import Any

from job_scout.adapters.base import SourceAdapter
from job_scout.config.settings import get_settings, load_sources

logger = logging.getLogger(__name__)


def _load_class(path: str) -> type[SourceAdapter]:
    module_name, _, cls_name = path.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, cls_name)


def inactive_source_names(sources_config: dict[str, Any] | None = None) -> set[str]:
    """Sources that are disabled, or skipped in CI, so health reports can ignore stale rows."""
    cfg = sources_config or load_sources()
    in_ci = get_settings().job_scout_env == "github"
    return {
        name
        for name, spec in (cfg.get("sources") or {}).items()
        if not spec.get("enabled", False) or (in_ci and spec.get("skip_in_ci"))
    }


def iter_adapters(
    *,
    pipeline: str | None = None,
    sources_config: dict[str, Any] | None = None,
    only_enabled: bool = True,
) -> list[SourceAdapter]:
    cfg = sources_config or load_sources()
    defaults = cfg.get("defaults") or {}
    adapters: list[SourceAdapter] = []
    in_ci = get_settings().job_scout_env == "github"
    for name, spec in (cfg.get("sources") or {}).items():
        if only_enabled and not spec.get("enabled", False):
            continue
        # Sites that refuse cloud-runner traffic: skip in GitHub Actions, run anywhere else.
        if in_ci and spec.get("skip_in_ci"):
            logger.info("Skipping %s in CI (site blocks cloud runners)", name)
            continue
        if pipeline and pipeline not in (spec.get("pipelines") or []):
            continue
        path = spec.get("adapter")
        if not path:
            continue
        merged = {**defaults, **spec, "name": name}
        try:
            cls = _load_class(path)
            adapters.append(cls(merged))
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not load adapter %s: %s", name, exc)
    return adapters
