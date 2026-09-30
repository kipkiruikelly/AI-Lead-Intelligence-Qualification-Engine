"""
pipeline/enricher.py
────────────────────
Step 2 — Company Research & Enrichment

For each discovered company:
  - Checks whether the website is reachable (HTTP HEAD, 5-second timeout)
  - Normalises all evidence fields with reliability labels:
      Verified  → confirmed via a specific public source URL
      Inferred  → reasonable inference from confirmed facts
      Unknown   → could not be determined from available sources

In production this module would also call:
  - Clearbit / Apollo for firmographic enrichment
  - Hunter.io for contact discovery
  - SerpAPI / Google Search for recent news
  - LinkedIn API or scraper for decision-maker identification

The function returns a dict that scorer.py and llm_client.py can consume.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 5  # seconds for website reachability check
_USER_AGENT = "LeadIntelligenceBot/1.0 (assessment prototype)"


def _check_website(url: str) -> bool | None:
    """
    Perform an HTTP HEAD request to determine if the website is reachable.

    Returns:
        True  — responded with any HTTP status
        False — connection error / timeout
        None  — URL is empty or malformed
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.head(
            url,
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
        reachable = resp.status_code < 500
        logger.debug("Website check %s → HTTP %d (reachable=%s)", url, resp.status_code, reachable)
        return reachable
    except requests.exceptions.Timeout:
        logger.warning("Website timeout: %s", url)
        return False
    except requests.exceptions.ConnectionError:
        logger.warning("Website unreachable (connection error): %s", url)
        return False
    except requests.exceptions.RequestException as exc:
        logger.warning("Website check failed for %s: %s", url, exc)
        return False


def _normalise_size(raw: str) -> str:
    """Map raw employee count to a standard SizeBand value."""
    mapping = {
        "51-200": "51-200",
        "201-500": "201-500",
        "1-50": "1-50",
        "501-1000": "501-1000",
    }
    return mapping.get(raw.strip(), "Unknown")


def _build_source_evidence(company: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert raw source URLs into structured SourceEvidence dicts.
    Website evidence is Verified; all other signals are tagged Inferred.
    """
    evidence: List[Dict[str, Any]] = []
    urls: List[str] = company.get("source_urls", [])
    evidence_label: str = company.get("evidence_status", "Unknown")

    for url in urls:
        if "linkedin.com" in url:
            evidence.append({
                "claim": f"LinkedIn company profile for {company.get('company', 'Unknown')}",
                "url": url,
                "evidence_status": "Verified",
            })
        elif url:
            evidence.append({
                "claim": f"Company website for {company.get('company', 'Unknown')}",
                "url": url,
                "evidence_status": "Verified",
            })

    # Exposure signals are inferred from the profile, not directly confirmed
    for signal in company.get("exposure_signals", []):
        evidence.append({
            "claim": f"Observed exposure signal: {signal}",
            "url": company.get("website", ""),
            "evidence_status": "Inferred",
        })

    # Regulatory signals are also inferred
    for reg in company.get("regulatory_signals", []):
        evidence.append({
            "claim": f"Regulatory/compliance context: {reg}",
            "url": "",
            "evidence_status": "Inferred",
        })

    return evidence


def enrich(
    company: Dict[str, Any],
    skip_website_check: bool = False,
) -> Dict[str, Any]:
    """
    Enrich a single company record with reliability labels and website status.

    Args:
        company:            Raw company dict from discoverer.
        skip_website_check: If True, skip HTTP check (speeds up dry runs).

    Returns:
        Enriched dict ready for scorer.py and llm_client.py.
    """
    enriched = dict(company)

    # ── Website reachability ──────────────────────────────────────────────────
    if skip_website_check:
        enriched["website_reachable"] = None  # Not checked
    else:
        enriched["website_reachable"] = _check_website(company.get("website", ""))

    # ── Size normalisation ────────────────────────────────────────────────────
    enriched["company_size"] = _normalise_size(
        company.get("employee_count_raw", "Unknown")
    )

    # ── Evidence structure ────────────────────────────────────────────────────
    enriched["source_evidence"] = _build_source_evidence(company)

    # ── Decision maker defaults ───────────────────────────────────────────────
    # We never invent a name. If not verified in source data, mark as such.
    dm_name = company.get("decision_maker_name", "Not verified")
    dm_title = company.get("decision_maker_title", "Not verified")
    dm_confidence = "Verified" if dm_name != "Not verified" else "Unknown"

    enriched["decision_maker"] = {
        "name": dm_name,
        "title": dm_title,
        "confidence": dm_confidence,
        "recommended_role": _recommend_role(company.get("industry", "")),
    }

    logger.debug(
        "Enriched '%s': website_reachable=%s, signals=%d",
        company.get("company"),
        enriched.get("website_reachable"),
        len(company.get("exposure_signals", [])),
    )
    return enriched


def _recommend_role(industry: str) -> str:
    """
    Return the most appropriate decision-maker role for cold outreach,
    based purely on industry classification.  This is a deterministic
    lookup — not AI.
    """
    industry_lower = industry.lower()
    if any(k in industry_lower for k in ["banking", "financial", "fintech", "insurance"]):
        return "CIO / IT Director / Information Security Lead"
    if "health" in industry_lower:
        return "IT Manager / Data Protection Lead / CTO"
    if "telecom" in industry_lower:
        return "CIO / IT Director / Head of Network Security"
    if any(k in industry_lower for k in ["technology", "it services", "software", "consulting"]):
        return "CTO / Information Security Lead / Head of IT"
    if "hospitality" in industry_lower or "hotel" in industry_lower:
        return "IT Manager / Operations Manager / General Manager"
    if any(k in industry_lower for k in ["logistics", "transport", "supply chain"]):
        return "IT Manager / Operations Technology Lead"
    return "IT Director / Head of Technology / CIO"
