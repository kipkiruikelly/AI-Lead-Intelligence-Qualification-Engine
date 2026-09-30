"""
pipeline/discoverer.py
─────────────────────
Step 1 — Lead Discovery

Loads providers dynamically based on config.yaml and CLI flags.
Deduplicates results and enforces provenance contracts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from pipeline.deduplicator import Deduplicator
from pipeline.providers.base import DiscoveryProvider
from pipeline.providers.web_search import WebSearchProvider
from pipeline.providers.seed_file import SeedFileProvider

logger = logging.getLogger(__name__)


def discover(
    config: Dict[str, Any],
    max_leads: int = 30,
    demo_mode: bool = False,
    seed_path: Path | None = None,
) -> List[Dict[str, Any]]:
    """
    Execute lead discovery using active provider(s).

    Args:
        config:     Parsed config.yaml target rules.
        max_leads:  Maximum number of unique leads to discover.
        demo_mode:  If True, explicit demo mode allows SeedFileProvider.
        seed_path:  Path to seed JSON file for demo mode.

    Returns:
        List of raw company candidates with discovery provenance.
    """
    target = config.get("target", {})
    provider_name = config.get("providers", {}).get("discovery", {}).get("primary", "web_search")

    providers: List[DiscoveryProvider] = []

    if demo_mode:
        if not seed_path:
            raise ValueError("seed_path required for demo_mode")
        logger.warning("DEMO MODE ACTIVE: Using historical seed file provider")
        providers.append(SeedFileProvider(seed_path))
    else:
        if provider_name == "web_search":
            providers.append(WebSearchProvider())
        else:
            logger.info("Defaulting to WebSearchProvider for live discovery")
            providers.append(WebSearchProvider())

    dedup = Deduplicator()
    discovered_leads: List[Dict[str, Any]] = []

    for provider in providers:
        if len(discovered_leads) >= max_leads:
            break

        logger.info("Executing discovery with provider: %s", provider.name)
        raw_candidates = provider.discover(target, max_leads - len(discovered_leads))

        for cand in raw_candidates:
            website = cand.get("website", "")
            company = cand.get("company", "")

            if not website or not company:
                logger.debug("Skipping candidate missing website or company name")
                continue

            if dedup.is_duplicate(website, company):
                logger.debug("Skipping duplicate candidate: %s (%s)", company, website)
                continue

            dedup.register(website, company)
            discovered_leads.append(cand)

            if len(discovered_leads) >= max_leads:
                break

    logger.info(
        "Discovery complete: %d unique candidates discovered (max limit: %d)",
        len(discovered_leads),
        max_leads,
    )
    return discovered_leads
