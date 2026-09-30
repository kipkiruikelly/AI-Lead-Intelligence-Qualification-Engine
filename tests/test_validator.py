"""
tests/test_validator.py
────────────────────────
Unit tests for Pydantic LeadRecord schema validation and template leak guards.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.validator import validate


def test_validator_template_leak_guard():
    invalid_data = {
        "company": "Test Co",
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
        "qualification_explanation": "Valid score explanation.",
        "business_observations": ["Obs 1"],
        "outreach_message": "Hello {first_name}, we provide cybersecurity services for {company_name}.",
        "decision_maker": {"name": "Not verified"},
    }

    record, error = validate(invalid_data, run_id="run_test_123")
    # Pydantic validator replaces {first_name} and {company_name} during coercion or throws error
    if record:
        assert "{first_name}" not in record.outreach_message
        assert "{company_name}" not in record.outreach_message
