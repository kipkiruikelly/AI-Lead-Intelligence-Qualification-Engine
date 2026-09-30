"""
tests/test_reproducibility.py
──────────────────────────────
Unit tests verifying deterministic scoring reproducibility.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scorer import score


def test_scoring_reproducibility_and_delta():
    enriched_base = {
        "company": "Stable Financials",
        "industry": "Financial Services",
        "company_size": "51-200",
        "description": "Financial institution providing banking services.",
        "exposure_signals": ["payment", "financial data"],
        "operational_signals": ["multi-branch environment"],
        "regulatory_signals": ["CBK regulated"],
        "recent_news": [],
        "source_evidence": [],
        "location": "Nairobi, Kenya",
    }
    config = {"scoring": {"high_threshold": 70, "medium_threshold": 50}}

    score1 = score(enriched_base, config)
    score2 = score(enriched_base, config)

    # Must be 100% reproducible
    assert score1["opportunity_score"] == score2["opportunity_score"]
    assert score1["score_breakdown"] == score2["score_breakdown"]
    assert score1["priority"] == score2["priority"]

    # Delta test: Modify single factor (add regulatory signal)
    enriched_modified = dict(enriched_base)
    enriched_modified["exposure_signals"] = ["payment", "financial data", "cloud infrastructure", "health records"]

    score3 = score(enriched_modified, config)
    assert score3["score_breakdown"]["exposure_score"] > score1["score_breakdown"]["exposure_score"]
    assert score3["opportunity_score"] > score1["opportunity_score"]
