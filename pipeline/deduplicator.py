"""
pipeline/deduplicator.py
────────────────────────
Canonical domain extraction and lead deduplication logic.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set
from urllib.parse import urlparse


def get_canonical_domain(url_or_name: str) -> str:
    """Extract canonical domain from URL or clean up company name."""
    if not url_or_name:
        return ""

    raw = url_or_name.strip().lower()

    if not raw.startswith(("http://", "https://")):
        raw = "http://" + raw

    try:
        parsed = urlparse(raw)
        domain = parsed.netloc or parsed.path
    except Exception:
        domain = raw

    # Strip port, 'www.', and trailing slash
    domain = domain.split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]

    # Remove query string/path if parsed via fallback
    domain = domain.split("/")[0]
    return domain.strip()


def normalize_company_name(name: str) -> str:
    """Normalize company name for fuzzy/exact string comparison."""
    if not name:
        return ""
    clean = name.lower().strip()
    # Strip common business entity suffixes
    clean = re.sub(r"\b(ltd|limited|inc|incorporated|corp|corporation|co|company|plc|llc|gmbh)\b", "", clean)
    clean = re.sub(r"[^\w\s]", "", clean)
    return " ".join(clean.split())


class Deduplicator:
    """Tracks seen canonical domains and normalized names during a pipeline run."""

    def __init__(self) -> None:
        self.seen_domains: Set[str] = set()
        self.seen_names: Set[str] = set()

    def is_duplicate(self, website: str, company_name: str) -> bool:
        domain = get_canonical_domain(website)
        norm_name = normalize_company_name(company_name)

        if domain and domain in self.seen_domains:
            return True
        if norm_name and norm_name in self.seen_names:
            return True

        return False

    def register(self, website: str, company_name: str) -> None:
        domain = get_canonical_domain(website)
        norm_name = normalize_company_name(company_name)

        if domain:
            self.seen_domains.add(domain)
        if norm_name:
            self.seen_names.add(norm_name)
