"""
pipeline/enricher.py
────────────────────
Step 2 — Company Research & Enrichment

Performs live HTTP request to company homepage, parses HTML title,
meta description, visible text, and technology/exposure signals.
Structures evidence with ISO UTC timestamps and reliability tags.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 8  # seconds timeout for live fetching
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _fetch_webpage_content(url: str) -> tuple[bool | None, str, str]:
    """
    Fetch webpage HTML content and extract title and meta description.

    Returns:
        (reachable, title, description_snippet)
    """
    if not url or not url.startswith(("http://", "https://")):
        return None, "", ""

    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        reachable = resp.status_code < 400

        if not reachable:
            return False, "", f"HTTP error {resp.status_code}"

        content_type = resp.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            return True, "", "Non-HTML content response"

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_el = soup.find("title")
        title = title_el.get_text(strip=True) if title_el else ""

        # Description meta
        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
        if not meta_desc:
            meta_desc = soup.find("meta", attrs={"property": re.compile(r"og:description", re.I)})

        desc = meta_desc.get("content", "").strip() if meta_desc else ""

        # Visible headings/text snippet fallback
        if not desc:
            p_tags = [p.get_text(strip=True) for p in soup.find_all(["p", "h1", "h2"]) if len(p.get_text(strip=True)) > 20]
            desc = " | ".join(p_tags[:3]) if p_tags else title

        return True, title[:150], desc[:500]

    except requests.exceptions.Timeout:
        logger.warning("Website request timeout for %s", url)
        return False, "", "Website timeout"
    except requests.exceptions.RequestException as exc:
        logger.warning("Website fetch failed for %s: %s", url, exc)
        return False, "", "Fetch failed"


def _extract_signals_from_text(text: str) -> Dict[str, List[str]]:
    """Scan retrieved page text for exposure, operational, and regulatory signals."""
    lower = text.lower()

    exposure_keywords = {
        "digital payments": ["payment", "checkout", "mpesa", "pos", "pay", "card", "transaction"],
        "customer PII": ["login", "register", "account", "profile", "customer data", "personal information"],
        "cloud infrastructure": ["cloud", "aws", "azure", "saas", "hosted", "api"],
        "financial data": ["banking", "loan", "credit", "finance", "investment", "kyc", "wallet"],
        "health records": ["patient", "medical", "health", "hospital", "doctor", "pharmacy"],
        "e-commerce transactions": ["cart", "shop", "ecommerce", "store", "order"],
    }

    regulatory_keywords = {
        "CBK regulated": ["central bank", "cbk"],
        "Data Protection Act": ["data protection", "privacy policy", "gdpr"],
        "PCI-DSS compliance": ["pci", "pci-dss", "card security"],
        "Ministry of Health": ["moh", "medical board", "pharmacy and poisons"],
    }

    operational_keywords = {
        "multi-branch environment": ["branches", "offices", "locations", "nationwide"],
        "regional operations": ["east africa", "regional", "africa", "global"],
        "distributed workforce": ["remote", "field teams", "24/7"],
    }

    found_exp = [label for label, kws in exposure_keywords.items() if any(kw in lower for kw in kws)]
    found_reg = [label for label, kws in regulatory_keywords.items() if any(kw in lower for kw in kws)]
    found_ops = [label for label, kws in operational_keywords.items() if any(kw in lower for kw in kws)]

    return {
        "exposure_signals": found_exp,
        "regulatory_signals": found_reg,
        "operational_signals": found_ops,
    }


def _recommend_role(industry: str) -> str:
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


def enrich(company: Dict[str, Any], skip_website_check: bool = False) -> Dict[str, Any]:
    """Enrich discovered lead with live web scraping and evidence attribution."""
    enriched = dict(company)
    now_iso = datetime.now(timezone.utc).isoformat()

    url = company.get("website", "")
    if skip_website_check:
        reachable = None
        title = ""
        desc = company.get("description", "Not checked")
    else:
        reachable, title, desc = _fetch_webpage_content(url)

    enriched["website_reachable"] = reachable
    if desc and len(desc) > 10:
        enriched["description"] = desc

    # Extract dynamic signals if web text available
    text_corpus = (title + " " + desc + " " + company.get("description", "")).strip()
    extracted = _extract_signals_from_text(text_corpus)

    # Combine extracted signals with any provider signals without duplicating
    enriched["exposure_signals"] = list(set(enriched.get("exposure_signals", []) + extracted["exposure_signals"]))
    enriched["regulatory_signals"] = list(set(enriched.get("regulatory_signals", []) + extracted["regulatory_signals"]))
    enriched["operational_signals"] = list(set(enriched.get("operational_signals", []) + extracted["operational_signals"]))

    # Standardize size
    enriched["company_size"] = company.get("company_size", "Unknown")

    # Source evidence with ISO UTC timestamps
    source_ev = []
    if url:
        source_ev.append({
            "claim": f"Company website: {title or company.get('company', 'Unknown')}",
            "url": url,
            "source_type": "company_website",
            "retrieved_at": now_iso,
            "evidence_text": desc[:300] if desc else None,
            "evidence_status": "Verified" if reachable else "Inferred",
        })

    for sig in enriched["exposure_signals"]:
        source_ev.append({
            "claim": f"Observed exposure signal: {sig}",
            "url": url,
            "source_type": "scraped_text_analysis",
            "retrieved_at": now_iso,
            "evidence_text": f"Matched in page snippet: {desc[:150]}",
            "evidence_status": "Inferred",
        })

    enriched["source_evidence"] = source_ev

    # Safe decision maker defaults
    dm_name = company.get("decision_maker_name", "Not verified")
    dm_title = company.get("decision_maker_title", "Not verified")

    enriched["decision_maker"] = {
        "name": dm_name,
        "title": dm_title,
        "profile_url": None,
        "source_url": url if dm_name != "Not verified" else None,
        "verification_status": "Verified" if dm_name != "Not verified" else "Unknown",
        "recommended_role": _recommend_role(company.get("industry", "")),
    }

    return enriched
