"""
pipeline/providers/web_search.py
────────────────────────────────
Live web search discovery provider using HTML/HTTP web query parsing
(DuckDuckGo / Bing Search fallback) without hardcoded static datasets.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from pipeline.providers.base import DiscoveryProvider

logger = logging.getLogger(__name__)

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_TIMEOUT = 10


class WebSearchProvider(DiscoveryProvider):
    """Live web search discovery provider."""

    @property
    def name(self) -> str:
        return "web_search"

    def _compile_queries(self, target_config: Dict[str, Any]) -> List[str]:
        industries = target_config.get("industries", ["technology"])
        geographies = target_config.get("geography", ["Kenya"])
        keywords = target_config.get("keywords", ["companies"])

        queries = []
        for geo in geographies[:2]:
            for ind in industries[:3]:
                for kw in keywords[:2]:
                    queries.append(f"{geo} {ind} {kw}")
                queries.append(f"top {ind} companies in {geo}")
        return queries

    def _execute_search(self, query: str) -> List[Dict[str, str]]:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}

        results = []
        try:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")

                for a in soup.find_all("a", class_="result__url"):
                    href = a.get("href", "").strip()
                    # Parse real destination from DDG redirect wrapper if present
                    if "uddg=" in href:
                        match = re.search(r"uddg=([^&]+)", href)
                        if match:
                            href = urllib.parse.unquote(match.group(1))

                    snippet_el = a.find_parent("div", class_="result__body")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if href.startswith(("http://", "https://")):
                        parsed = urllib.parse.urlparse(href)
                        domain = parsed.netloc.replace("www.", "").split(":")[0]
                        # Exclude generic directories / search engine links
                        if domain and not any(x in domain for x in ["duckduckgo.com", "bing.com", "google.com", "wikipedia.org", "youtube.com", "facebook.com", "linkedin.com/search"]):
                            company_name = domain.split(".")[0].replace("-", " ").title()
                            results.append({
                                "company": company_name,
                                "website": f"https://{domain}",
                                "source_url": href,
                                "snippet": snippet[:200]
                            })
        except Exception as exc:
            logger.warning("WebSearchProvider search failed for query '%s': %s", query, exc)

        return results

    def discover(self, target_config: Dict[str, Any], max_leads: int) -> List[Dict[str, Any]]:
        queries = self._compile_queries(target_config)
        logger.info("WebSearchProvider compiled %d search queries", len(queries))

        discovered = []
        seen_domains = set()

        for q in queries:
            if len(discovered) >= max_leads:
                break
            logger.debug("Executing live search query: '%s'", q)
            raw_results = self._execute_search(q)

            for res in raw_results:
                domain = res["website"]
                if domain in seen_domains:
                    continue
                seen_domains.add(domain)

                discovered.append({
                    "company": res["company"],
                    "website": res["website"],
                    "industry": target_config.get("industries", ["Technology"])[0],
                    "location": target_config.get("geography", ["Kenya"])[0],
                    "employee_count_raw": "Unknown",
                    "description": res.get("snippet", f"Discovered via search query: {q}"),
                    "discovery_source": self.name,
                    "discovery_query": q,
                    "source_url": res["source_url"],
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "raw_source_reference": f"WebSearchQuery: {q}",
                    "exposure_signals": [],
                    "operational_signals": [],
                    "regulatory_signals": [],
                    "recent_news": [],
                    "decision_maker_name": "Not verified",
                    "decision_maker_title": "Not verified",
                    "evidence_status": "Inferred",
                })

                if len(discovered) >= max_leads:
                    break

        logger.info("WebSearchProvider found %d raw lead candidates", len(discovered))
        return discovered
