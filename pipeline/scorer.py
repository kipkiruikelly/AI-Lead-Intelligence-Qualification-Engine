"""
pipeline/scorer.py
──────────────────
Step 3 — Deterministic Qualification & Scoring

The score is calculated entirely with objective business rules.
The LLM is NOT involved in scoring or qualification decisions.

Score breakdown (0-100):
  size_score       0-20  — employee band
  sector_score     0-25  — industry risk profile
  exposure_score   0-25  — digital/data exposure signals (+5 each, max 25)
  complexity_score 0-10  — operational complexity signals
  regulatory_score 0-10  — regulatory sensitivity evidence
  bonus_score      0-10  — bonus signals (digital transformation, recent tech hire)

Thresholds (from config):
  >= high_threshold  → High Priority  / Qualified
  >= mid_threshold   → Medium Priority / Qualified
  <  mid_threshold   → Low Priority   / Needs Review
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SIZE_SCORES: Dict[str, int] = {
    "51-200": 15,
    "201-500": 20,
    "Unknown": 10,  # conservative default
}

SECTOR_SCORES: Dict[str, int] = {
    "banking": 25,
    "financial services": 25,
    "fintech": 25,
    "insurance": 22,
    "hospitals and health care": 25,
    "healthcare": 25,
    "telecommunications": 20,
    "technology, information and internet": 18,
    "information technology & services": 15,
    "it services and it consulting": 15,
    "operations consulting": 10,
    "business consulting and services": 8,
    "hospitality": 10,
    "transportation, logistics, supply chain and storage": 12,
    "logistics": 12,
}

# Exposure signals: each match adds EXPOSURE_SIGNAL_POINTS (max EXPOSURE_MAX)
EXPOSURE_SIGNAL_POINTS = 5
EXPOSURE_MAX = 25

HIGH_VALUE_SIGNALS = {
    "payment", "financial data", "health", "medical", "kyc", "pii",
    "customer data", "e-commerce", "transaction", "lending", "credit",
    "banking system", "insurance", "pension", "ai/ml", "cloud",
    "saas", "multi-system", "api integration", "identity", "biometric",
}

# Operational complexity signals
COMPLEXITY_SIGNALS = {
    "multi-site", "multi-branch", "multi-location", "regional", "distributed",
    "cross-border", "pan-african", "multi-country", "nationwide", "multiple facilities",
    "subcontractor", "multi-client",
}

# Regulatory signals
REGULATORY_SIGNALS = {
    "cbk", "cma", "moh", "ira kenya", "nse", "rba", "pharmacy",
    "pci-dss", "gdpr", "aml", "kyc", "iso", "kcaa", "kra",
    "regulation", "licensed", "regulated", "compliance",
}

# Bonus signals
BONUS_SIGNALS = {
    "digital transformation": 5,
    "funding round": 5,
    "new facility": 3,
    "expansion": 3,
    "new hire": 5,
    "tech hire": 5,
    "new f&b": 2,
}


def _score_size(company_size: str) -> int:
    return SIZE_SCORES.get(company_size.strip(), 10)


def _score_sector(industry: str) -> int:
    il = industry.lower()
    # Exact match first
    if il in SECTOR_SCORES:
        return SECTOR_SCORES[il]
    # Partial match — take the highest scoring match
    best = 5  # fallback minimum
    for key, pts in SECTOR_SCORES.items():
        if key in il or il in key:
            best = max(best, pts)
    return best


def _score_exposure(signals: List[str]) -> int:
    total = 0
    matched = set()
    for signal in signals:
        sl = signal.lower()
        for keyword in HIGH_VALUE_SIGNALS:
            if keyword in sl and keyword not in matched:
                matched.add(keyword)
                total += EXPOSURE_SIGNAL_POINTS
                if total >= EXPOSURE_MAX:
                    return EXPOSURE_MAX
    return min(total, EXPOSURE_MAX)


def _score_complexity(
    operational_signals: List[str], location: str
) -> int:
    combined = " ".join(operational_signals).lower() + " " + location.lower()
    for kw in COMPLEXITY_SIGNALS:
        if kw in combined:
            return 10
    return 0


def _score_regulatory(
    regulatory_signals: List[str], source_evidence: List[Dict[str, Any]]
) -> int:
    combined = " ".join(regulatory_signals).lower()
    # Also check source evidence claims
    for ev in source_evidence:
        combined += " " + ev.get("claim", "").lower()
    for kw in REGULATORY_SIGNALS:
        if kw in combined:
            return 10
    return 0


def _score_bonus(recent_news: List[str], description: str) -> int:
    combined = " ".join(recent_news).lower() + " " + description.lower()
    total = 0
    for phrase, pts in BONUS_SIGNALS.items():
        if phrase in combined:
            total += pts
    return min(total, 10)


def _determine_qualification(
    score: int, high_threshold: int, mid_threshold: int
) -> tuple[str, str]:
    """Returns (qualification_status, priority)."""
    if score >= high_threshold:
        return "Qualified", "High Priority"
    if score >= mid_threshold:
        return "Qualified", "Medium Priority"
    return "Needs Review", "Low Priority"


def score(enriched: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate a fully deterministic opportunity score for one company.

    Args:
        enriched: Output from enricher.enrich()
        config:   Parsed config.yaml dict

    Returns:
        enriched dict updated with score_breakdown, opportunity_score,
        priority, and qualification_status.
    """
    scoring_cfg = config.get("scoring", {})
    high_threshold = int(scoring_cfg.get("high_threshold", 70))
    mid_threshold = int(scoring_cfg.get("medium_threshold", 50))

    company_size = enriched.get("company_size", "Unknown")
    industry = enriched.get("industry", "")
    exposure_signals = enriched.get("exposure_signals", [])
    operational_signals = enriched.get("operational_signals", [])
    regulatory_signals = enriched.get("regulatory_signals", [])
    recent_news = enriched.get("recent_news", [])
    description = enriched.get("description", "")
    source_evidence = enriched.get("source_evidence", [])
    location = enriched.get("location", "")

    size_score = _score_size(company_size)
    sector_score = _score_sector(industry)
    exposure_score = _score_exposure(exposure_signals)
    complexity_score = _score_complexity(operational_signals, location)
    regulatory_score = _score_regulatory(regulatory_signals, source_evidence)
    bonus_score = _score_bonus(recent_news, description)

    total = (
        size_score
        + sector_score
        + exposure_score
        + complexity_score
        + regulatory_score
        + bonus_score
    )
    total = min(total, 100)

    qual_status, priority = _determine_qualification(
        total, high_threshold, mid_threshold
    )

    enriched["score_breakdown"] = {
        "size_score": size_score,
        "sector_score": sector_score,
        "exposure_score": exposure_score,
        "complexity_score": complexity_score,
        "regulatory_score": regulatory_score,
        "bonus_score": bonus_score,
        "total": total,
    }
    enriched["opportunity_score"] = total
    enriched["priority"] = priority
    enriched["qualification_status"] = qual_status

    logger.debug(
        "Scored '%s': %d (%s) — size=%d sector=%d exposure=%d "
        "complexity=%d regulatory=%d bonus=%d",
        enriched.get("company"),
        total,
        priority,
        size_score,
        sector_score,
        exposure_score,
        complexity_score,
        regulatory_score,
        bonus_score,
    )
    return enriched
