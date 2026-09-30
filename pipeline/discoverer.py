"""
pipeline/discoverer.py
─────────────────────
Step 1 — Lead Discovery

Loads seed_companies.json and filters the records against the targeting
criteria in config.yaml (industry, size band, geography).

In production this module would call an external search/company-data API
(e.g. Apollo, Hunter, SerpAPI, LinkedIn Sales Navigator).  The seed file
simulates that discovery step so the pipeline runs without paid credentials.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Size-band normalisation ────────────────────────────────────────────────────

_SIZE_BANDS: Dict[str, tuple[int, int]] = {
    "51-200": (51, 200),
    "201-500": (201, 500),
    "1-50": (1, 50),
    "501-1000": (501, 1000),
}


def _parse_size_band(raw: str) -> tuple[int, int] | None:
    """Convert a raw employee-count string to (min, max) tuple."""
    raw = raw.strip()
    if raw in _SIZE_BANDS:
        return _SIZE_BANDS[raw]
    # Try numeric parse for single values
    try:
        n = int(raw)
        return (n, n)
    except ValueError:
        return None


def _in_size_range(raw: str, emp_min: int, emp_max: int) -> bool:
    band = _parse_size_band(raw)
    if band is None:
        logger.warning("Could not parse size band '%s'; including by default", raw)
        return True
    lo, hi = band
    # Overlap: company band overlaps with target range
    return lo <= emp_max and hi >= emp_min


# ── Normalise industry label ───────────────────────────────────────────────────

def _industry_matches(company_industry: str, target_industries: List[str]) -> bool:
    """Case-insensitive substring match against configured industry list."""
    ci = company_industry.lower()
    for t in target_industries:
        if t.lower() in ci or ci in t.lower():
            return True
    return False


def _geography_matches(location: str, geographies: List[str]) -> bool:
    """Check that at least one configured geography appears in the location."""
    loc = location.lower()
    for g in geographies:
        if g.lower() in loc:
            return True
    return False


# ── Public API ─────────────────────────────────────────────────────────────────

def discover(config: Dict[str, Any], seed_path: Path) -> List[Dict[str, Any]]:
    """
    Load seed companies, apply targeting filters, return matching records.

    Args:
        config:    Parsed config.yaml dict.
        seed_path: Path to seed_companies.json.

    Returns:
        List of raw company dicts that passed all filters.
    """
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")

    with seed_path.open(encoding="utf-8") as fh:
        raw: List[Dict[str, Any]] = json.load(fh)

    target = config.get("target", {})
    industries: List[str] = target.get("industries", [])
    geographies: List[str] = target.get("geography", [])
    emp_min: int = int(target.get("employee_min", 50))
    emp_max: int = int(target.get("employee_max", 500))

    accepted: List[Dict[str, Any]] = []
    excluded_count = 0

    for company in raw:
        name = company.get("company", "Unknown")

        # Geography filter
        if geographies and not _geography_matches(
            company.get("location", ""), geographies
        ):
            logger.debug("Excluded '%s': geography mismatch", name)
            excluded_count += 1
            continue

        # Industry filter
        if industries and not _industry_matches(
            company.get("industry", ""), industries
        ):
            logger.debug("Excluded '%s': industry mismatch", name)
            excluded_count += 1
            continue

        # Size filter
        if not _in_size_range(
            company.get("employee_count_raw", ""), emp_min, emp_max
        ):
            logger.debug("Excluded '%s': size out of range", name)
            excluded_count += 1
            continue

        accepted.append(company)

    logger.info(
        "Discovery: %d companies loaded, %d accepted, %d excluded by filter",
        len(raw),
        len(accepted),
        excluded_count,
    )
    return accepted
