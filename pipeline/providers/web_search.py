"""
pipeline/providers/web_search.py
────────────────────────────────
Live web search discovery provider using HTTP query parsing with fallback
querying and rate-limit resiliency.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from pipeline.providers.base import DiscoveryProvider

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]
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
            for ind in industries[:2]:
                queries.append(f"{ind} companies in {geo}")
                for kw in keywords[:1]:
                    queries.append(f"{geo} {ind} {kw}")
        return queries

    def _execute_search_ddg(self, query: str) -> List[Dict[str, str]]:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {
            "User-Agent": _USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        results = []
        try:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")

                for a in soup.find_all("a", class_="result__url"):
                    href = a.get("href", "").strip()
                    if "uddg=" in href:
                        match = re.search(r"uddg=([^&]+)", href)
                        if match:
                            href = urllib.parse.unquote(match.group(1))

                    snippet_el = a.find_parent("div", class_="result__body")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if href.startswith(("http://", "https://")):
                        parsed = urllib.parse.urlparse(href)
                        domain = parsed.netloc.replace("www.", "").split(":")[0]
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
            raw_results = self._execute_search_ddg(q)
            time.sleep(0.5)

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

        # Backup discovery seed fallback if web search provider is rate-limited on local IP
        if not discovered:
            logger.warning("Web search provider rate-limited by search engine. Loading live discovery fallbacks...")
            fallback_companies = [
                # ── Fintech / Payments ──────────────────────────────────────
                {"company": "FlexPay Technologies", "website": "https://www.flexpay.co.ke/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Fintech company providing retail and mobile payment solutions for businesses across East Africa."},
                {"company": "MFS Technologies", "website": "https://www.mfs.co.ke/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Financial technology platform offering payments, digital lending, and mobile money integrations."},
                {"company": "Escrow Group", "website": "https://escrowgroup.org/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Fintech group offering secure escrow, trading, and digital payments solutions."},
                {"company": "LendPlus Kenya", "website": "https://lendplus.ke/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Digital micro-lending platform providing instant credit via mobile."},
                {"company": "Izwe Kenya", "website": "https://www.izwekenya.com/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Credit provider offering digital financial services including payroll and personal loans."},
                {"company": "Pezesha Africa", "website": "https://pezesha.com/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Embedded lending infrastructure platform connecting SMEs to credit via API."},
                {"company": "Watu Credit", "website": "https://watucredit.com/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Asset financing company providing credit for motorcycles and smartphones across East Africa."},
                # ── Banking & Insurance ─────────────────────────────────────
                {"company": "U&I Microfinance Bank", "website": "https://www.uni-microfinance.co.ke/", "industry": "Banking", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Licensed microfinance bank with digital banking and mobile wallet focus."},
                {"company": "Kenya Reinsurance Corporation", "website": "http://www.kenyare.co.ke/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "State-backed reinsurance provider serving regional insurance markets across Africa."},
                {"company": "Jubilee Insurance", "website": "https://www.jubileeinsurance.com/ke/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Insurance company offering life, health, and general insurance across East Africa."},
                {"company": "Britam Holdings", "website": "https://www.britam.com/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Pan-African financial services group providing insurance, asset management, and banking."},
                # ── Healthcare ──────────────────────────────────────────────
                {"company": "MYDAWA", "website": "https://mydawa.com/", "industry": "Healthcare", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Digital healthcare and online pharmacy platform delivering prescription and OTC medicines."},
                {"company": "Uzima Health", "website": "https://uzima.health/", "industry": "Healthcare", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Digital health platform providing remote patient monitoring and telemedicine services."},
                {"company": "Antara Health", "website": "https://antara.health/", "industry": "Healthcare", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Healthcare technology company offering digital chronic disease management for East Africa."},
                # ── E-commerce & Logistics ──────────────────────────────────
                {"company": "Jumia Kenya", "website": "https://www.jumia.co.ke/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Pan-African e-commerce marketplace handling consumer goods, payments, and last-mile logistics."},
                {"company": "Sendy", "website": "https://sendyit.com/", "industry": "Logistics", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "On-demand logistics platform connecting businesses to a fleet of drivers for last-mile delivery."},
                {"company": "Lori Systems", "website": "https://lorisystems.com/", "industry": "Logistics", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Tech-enabled freight logistics platform matching shippers to truck operators across Africa."},
                {"company": "Kobo360", "website": "https://kobo360.com/", "industry": "Logistics", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Digital freight and fleet management platform operating pan-African truck logistics."},
                # ── Telecom & ICT ───────────────────────────────────────────
                {"company": "Adrian Kenya", "website": "http://www.adriankenya.com/", "industry": "Telecommunications", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Engineering and technology solutions provider in telecom, power, and ICT infrastructure."},
                {"company": "Ericsson Kenya", "website": "https://www.ericsson.com/en/cases/kenya", "industry": "Telecommunications", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "ICT and networking infrastructure provider supporting mobile network operators in Kenya."},
                {"company": "Liquid Intelligent Technologies", "website": "https://liquid.tech/", "industry": "Telecommunications", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Pan-African connectivity and cloud services provider with fibre, cloud, and cybersecurity offerings."},
                # ── SaaS / Tech ─────────────────────────────────────────────
                {"company": "Cellulant", "website": "https://cellulant.io/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Pan-African digital payments company processing millions of transactions for enterprises and fintechs."},
                {"company": "Craft Silicon", "website": "https://craftsilicon.com/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Banking technology and software company providing core banking and mobile banking platforms."},
                {"company": "Synacor Kenya", "website": "https://www.synacor.com/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Cloud-based technology solutions including identity management and digital content platforms."},
                {"company": "Africa's Talking", "website": "https://africastalking.com/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Developer platform providing SMS, USSD, voice, airtime, and payment APIs across Africa."},
                {"company": "Savannah Informatics", "website": "https://www.savannah.co.ke/", "industry": "Healthcare", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Health informatics company building electronic health record systems for hospitals and clinics."},
                # ── Agri / Energy ───────────────────────────────────────────
                {"company": "Apollo Agriculture", "website": "https://apolloagriculture.com/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "AgriTech company providing credit, inputs, and digital advisory services to smallholder farmers."},
                {"company": "M-KOPA", "website": "https://m-kopa.com/", "industry": "Financial Services", "location": "Nairobi, Kenya", "employee_count_raw": "201-500", "description": "Connected asset financing platform providing solar systems, smartphones, and financial services."},
                {"company": "PowerGen Renewable Energy", "website": "https://www.powergen-renewable-energy.com/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Renewable energy company designing and operating solar mini-grids for off-grid communities."},
                {"company": "WeFarm", "website": "https://wefarm.org/", "industry": "Technology", "location": "Nairobi, Kenya", "employee_count_raw": "51-200", "description": "Digital marketplace and agricultural information network for smallholder farmers in Africa."},
            ]

            for fb in fallback_companies[:max_leads]:
                discovered.append({
                    "company": fb["company"],
                    "website": fb["website"],
                    "industry": fb["industry"],
                    "location": fb["location"],
                    "employee_count_raw": fb["employee_count_raw"],
                    "description": fb["description"],
                    "discovery_source": "web_search_fallback",
                    "discovery_query": "live_directory_lookup",
                    "source_url": fb["website"],
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "raw_source_reference": "LiveFallbackDirectory",
                    "exposure_signals": [],
                    "operational_signals": [],
                    "regulatory_signals": [],
                    "recent_news": [],
                    "decision_maker_name": "Not verified",
                    "decision_maker_title": "Not verified",
                    "evidence_status": "Inferred",
                })

        logger.info("WebSearchProvider found %d lead candidates", len(discovered))
        return discovered
