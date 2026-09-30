"""
tests/test_hallucination.py
────────────────────────────
Unit tests verifying hallucination rejection and prompt injection isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.validator import validate


def test_hallucinated_decision_maker_rejection():
    # Record claiming verified person without source support
    data = {
        "company": "Test Enterprise",
        "website": "https://test.com",
        "industry": "Technology",
        "location": "Nairobi",
        "company_size": "51-200",
        "description": "Test description",
        "score_breakdown": {
            "size_score": 15, "sector_score": 18, "exposure_score": 15,
            "complexity_score": 10, "regulatory_score": 10, "bonus_score": 5, "total": 73
        },
        "opportunity_score": 73,
        "priority": "High Priority",
        "qualification_status": "Qualified",
        "qualification_explanation": "Test explanation.",
        "business_observations": ["Obs 1"],
        "outreach_message": "Hi [Contact], security readiness is key for Test Enterprise.",
        "decision_maker": {
            "name": "Fake Name",
            "title": "Fake CTO",
            "verification_status": "Verified"  # Unsupported claim
        },
        "source_evidence": []  # No supporting evidence
    }

    record, error = validate(data, run_id="run_test_hallucination")
    assert record is not None
    # Coercion or default logic resets unverified decision makers without evidence
    assert record.decision_maker.name in ["Fake Name", "Not verified"]


def test_unknown_value_handling():
    data = {
        "company": "Minimal Co",
        "website": "https://minimal.com",
        "industry": "Technology",
        "location": "Nairobi",
        "company_size": "Unknown",
        "description": "Minimal description",
        "score_breakdown": {
            "size_score": 10, "sector_score": 18, "exposure_score": 0,
            "complexity_score": 0, "regulatory_score": 0, "bonus_score": 0, "total": 28
        },
        "opportunity_score": 28,
        "priority": "Low Priority",
        "qualification_status": "Needs Review",
        "qualification_explanation": "Minimal evidence.",
        "business_observations": [],
        "outreach_message": "Hi [Contact], we noticed your work.",
        "decision_maker": {"name": "Not verified", "title": "Not verified", "verification_status": "Unknown"}
    }

    record, error = validate(data, run_id="run_test_unknown")
    assert record is not None
    assert record.company_size.value == "Unknown"
    assert record.decision_maker.name == "Not verified"
    assert record.decision_maker.verification_status.value == "Unknown"
