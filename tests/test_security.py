"""
tests/test_security.py
───────────────────────
Unit tests for SSRF protection and unsafe URL blocking.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.security import is_safe_url


def test_ssrf_blocks_private_and_loopback_urls():
    assert not is_safe_url("http://127.0.0.1")
    assert not is_safe_url("http://localhost")
    assert not is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert not is_safe_url("http://10.0.0.1")
    assert not is_safe_url("http://192.168.1.1")
    assert not is_safe_url("ftp://example.com")
    assert not is_safe_url("javascript:alert(1)")


def test_ssrf_allows_valid_public_urls():
    assert is_safe_url("https://www.google.com")
    assert is_safe_url("https://mydawa.com")
