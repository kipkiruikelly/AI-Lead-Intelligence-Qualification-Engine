"""
tests/test_scorer.py
───────────────────
Unit tests for deterministic 6-factor scoring engine.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scorer import score


def test_scorer_deterministic_calculation():
    enriched = {
        "company": "Acme Bank",
        "industry": "Banking",
        "company_size": "201-500",
        "description": "Licensed bank offering cloud-based micro-loans and payment processing.",
        "exposure_signals": ["payment", "cloud infrastructure", "financial data"],
        "operational_signals": ["multi-branch environment"],
        "regulatory_signals": ["CBK regulated"],
        "recent_news": ["digital transformation"],
        "source_evidence": [],
        "location": "Nairobi, Kenya",
        "decision_maker": {"name": "Not verified"},
    }

    config = {
        "scoring": {
            "high_threshold": 70,
            "medium_threshold": 50,
        }
    }

    scored = score(enriched, config)
    sb = scored["score_breakdown"]

    assert sb["size_score"] == 20
    assert sb["sector_score"] == 25
    assert sb["exposure_score"] == 15
    assert sb["complexity_score"] == 10
    assert sb["regulatory_score"] == 10
    assert sb["bonus_score"] == 5
    assert scored["opportunity_score"] == 85
    assert scored["priority"] == "High Priority"
    assert scored["qualification_status"] == "Qualified"


def test_scorer_unknown_size_handling():
    enriched = {
        "company": "Unknown Start-up",
        "industry": "IT Services",
        "company_size": "Unknown",
        "exposure_signals": [],
        "operational_signals": [],
        "regulatory_signals": [],
        "recent_news": [],
        "source_evidence": [],
        "location": "Nairobi, Kenya",
    }

    config = {"scoring": {"high_threshold": 70, "medium_threshold": 50}}
    scored = score(enriched, config)

    assert scored["score_breakdown"]["size_score"] == 10
    assert scored["opportunity_score"] < 50
    assert scored["priority"] == "Low Priority"
