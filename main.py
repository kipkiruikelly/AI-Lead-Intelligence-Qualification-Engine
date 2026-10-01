#!/usr/bin/env python3
"""
main.py — AI-Powered Lead Intelligence & Qualification Engine

Orchestrates lead discovery, research enrichment, deterministic scoring,
LLM structured analysis, schema validation, and persistence.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from pipeline.discoverer import discover
from pipeline.enricher import enrich
from pipeline.scorer import score
from pipeline.llm_client import analyse
from pipeline.validator import validate_batch
from pipeline.output_writer import write_all
from pipeline.repository import LeadRepository


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    for lib in ("urllib3", "httpx", "httpcore", "google"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def _load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg


def run_pipeline(args: argparse.Namespace) -> int:
    logger = logging.getLogger("main")
    start_time = time.time()

    # Generate unique run ID
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{now_str}_{uuid.uuid4().hex[:4]}"

    config_path = ROOT / args.config
    config = _load_config(config_path)

    output_dir = ROOT / args.output_dir
    db_path = output_dir / "leads_repository.db"
    seed_path = ROOT / "data" / "seed_companies.json"

    demo_mode = args.demo_mode
    skip_llm = args.skip_llm

    if not skip_llm and not demo_mode:
        has_gemini = bool(os.getenv("GEMINI_API_KEY"))
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        if not has_gemini and not has_openai:
            logger.warning("No GEMINI_API_KEY or OPENAI_API_KEY found. LLM synthesis will be disabled.")
            skip_llm = True

    max_leads = int(config.get("target", {}).get("max_leads", 30))

    print("\n" + "═" * 65)
    print("  🔐 AI Lead Intelligence & Qualification Engine")
    print(f"  Run ID:     {run_id}")
    print(f"  Mode:       {'DEMO MODE (Static Seed File)' if demo_mode else 'LIVE MODE (Web Search Discovery & Scraping)'}")
    print(f"  Max Leads:  {max_leads}")
    print(f"  Output Dir: {output_dir}")
    print("═" * 65 + "\n")

    # Step 1: Discovery
    print("Step 1/5 — Lead Discovery")
    companies = discover(config, max_leads=max_leads, demo_mode=demo_mode, seed_path=seed_path)
    print(f"  ✓ {len(companies)} company candidates discovered\n")

    if not companies:
        logger.error("No companies discovered. Check query parameters or web access.")
        return 1

    if args.dry_run:
        print("Dry run complete. Discovered leads:")
        for c in companies:
            print(f"  • {c['company']} ({c['website']}) — Source: {c.get('discovery_source')}")
        return 0

    # Step 2: Enrichment
    print("Step 2/5 — Live Web Scraping & Evidence Extraction")
    enriched_list = []
    for i, comp in enumerate(companies, 1):
        print(f"\r  [{i}/{len(companies)}] Fetching & scraping: {comp['company'][:35]:<35}", end="", flush=True)
        enriched = enrich(comp, skip_website_check=args.skip_website_check)
        enriched_list.append(enriched)
    print("\n  ✓ Research enrichment complete\n")

    # Step 3: Scoring
    print("Step 3/5 — Deterministic Scoring Engine")
    scored_list = []
    for en in enriched_list:
        scored = score(en, config)
        scored_list.append(scored)

    high = sum(1 for s in scored_list if s["priority"] == "High Priority")
    med = sum(1 for s in scored_list if s["priority"] == "Medium Priority")
    low = sum(1 for s in scored_list if s["priority"] == "Low Priority")
    print(f"  ✓ Scoring complete: High={high}, Medium={med}, Low={low}\n")

    # Step 4: LLM Analysis
    print("Step 4/5 — LLM Structured Analysis")
    analysed_list = []
    llm_success = 0
    for i, sc in enumerate(scored_list, 1):
        print(f"\r  [{i}/{len(scored_list)}] LLM Analyzing: {sc['company'][:35]:<35}", end="", flush=True)
        analysed = analyse(sc, config, skip_llm=skip_llm, demo_mode=demo_mode)
        analysed_list.append(analysed)
        if analysed.get("llm_used"):
            llm_success += 1
    print(f"\n  ✓ Analysis complete: LLM-processed={llm_success}/{len(analysed_list)}\n")

    # Step 5: Validation
    print("Step 5/5 — Pydantic Validation Gate & Persistence")
    valid_records, review_queue = validate_batch(analysed_list, run_id=run_id)
    print(f"  ✓ Valid: {len(valid_records)} | Review Queue: {len(review_queue)}\n")

    # Step 6: Database & File Output
    elapsed = round(time.time() - start_time, 2)
    metadata = {
        "run_id": run_id,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "mode": "demo" if demo_mode else "live",
        "discovery_provider": "seed_file_demo" if demo_mode else "web_search",
        "total_discovered": len(companies),
        "total_valid": len(valid_records),
        "total_review_queue": len(review_queue),
        "llm_used_count": llm_success,
        "skip_llm": skip_llm,
    }

    # Save to SQLite Database
    repo = LeadRepository(db_path)
    repo.save_run(run_id, metadata, valid_records)

    # Export Files
    write_all(valid_records, review_queue, metadata, output_dir)

    print("═" * 65)
    print("  ✅ Pipeline Run Completed Successfully!")
    print(f"  Run ID:        {run_id}")
    print(f"  Elapsed:       {elapsed}s")
    print(f"  Latest Output: {output_dir / 'latest' / 'dashboard.html'}")
    print(f"  Run Folder:    {output_dir / 'runs' / run_id}")
    print(f"  Database:      {db_path}")
    print("═" * 65 + "\n")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Lead Intelligence Engine")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--demo-mode", action="store_true", help="Explicitly enable static seed dataset for demo/testing")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-website-check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()
    _setup_logging(args.verbose)
    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
