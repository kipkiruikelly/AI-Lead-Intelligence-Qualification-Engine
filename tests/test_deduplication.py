"""
tests/test_deduplication.py
───────────────────────────
Unit tests for canonical domain deduplication.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.deduplicator import Deduplicator, get_canonical_domain, normalize_company_name


def test_canonical_domain_parsing():
    assert get_canonical_domain("https://www.example.co.ke/path/page") == "example.co.ke"
    assert get_canonical_domain("http://example.co.ke") == "example.co.ke"
    assert get_canonical_domain("example.co.ke:8080") == "example.co.ke"


def test_normalize_company_name():
    assert normalize_company_name("FlexPay Technologies Ltd.") == "flexpay technologies"
    assert normalize_company_name("Jumia Kenya PLC") == "jumia kenya"


def test_deduplicator():
    dedup = Deduplicator()
    assert not dedup.is_duplicate("https://www.example.com", "Example Corp")

    dedup.register("https://www.example.com", "Example Corp")

    assert dedup.is_duplicate("http://example.com/about", "Another Name")
    assert dedup.is_duplicate("https://different.com", "Example Corporation")
