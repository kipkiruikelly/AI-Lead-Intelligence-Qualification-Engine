#!/usr/bin/env python3
"""
main.py — AI-Powered Lead Intelligence & Qualification Engine
═════════════════════════════════════════════════════════════
End-to-end pipeline CLI for discovering, enriching, scoring, analysing,
and generating outreach for cybersecurity consulting prospects.

Pipeline stages:
  Step 1  discoverer.py  — load seed companies, apply config filters
  Step 2  enricher.py    — website check, evidence normalisation
  Step 3  scorer.py      — deterministic opportunity scoring (0-100)
  Step 4  llm_client.py  — LLM structured analysis & outreach (optional)
  Step 5  validator.py   — Pydantic schema validation gate
  Step 10 output_writer  — CSV, JSON, HTML dashboard

Usage:
  python main.py                          # full run (LLM if API key present)
  python main.py --skip-llm              # deterministic only, no API key needed
  python main.py --config custom.yaml    # use a different targeting config
  python main.py --output-dir ./results  # custom output directory
  python main.py --dry-run               # discovery + scoring only, no output files
  python main.py --validate-only         # validate existing leads_output.json

Run 'python main.py --help' for all options.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from pipeline.discoverer import discover
from pipeline.enricher import enrich
from pipeline.scorer import score
from pipeline.llm_client import analyse
from pipeline.validator import validate_batch
from pipeline.output_writer import write_all

# ── Logging ────────────────────────────────────────────────────────────────────

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Quieten noisy libraries
    for lib in ("urllib3", "httpx", "httpcore", "google"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ── Config loading ─────────────────────────────────────────────────────────────

def _load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open(encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not isinstance(cfg, dict):
        raise ValueError("config.yaml must be a YAML mapping")
    return cfg


# ── Progress display ───────────────────────────────────────────────────────────

def _progress(current: int, total: int, label: str, width: int = 30) -> None:
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total)
    print(f"\r  [{bar}] {pct:3d}%  {label:<40}", end="", flush=True)
    if current == total:
        print()


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> int:
    """
    Execute the full pipeline and return exit code (0 = success).
    """
    logger = logging.getLogger("main")
    start_time = time.time()

    # ── Config ────────────────────────────────────────────────────────────────
    config_path = ROOT / args.config
    logger.info("Loading config: %s", config_path)
    config = _load_config(config_path)

    output_dir = ROOT / args.output_dir
    seed_path = ROOT / "data" / "seed_companies.json"

    # ── LLM availability check ────────────────────────────────────────────────
    skip_llm = args.skip_llm
    if not skip_llm:
        has_gemini = bool(os.getenv("GEMINI_API_KEY"))
        has_openai = bool(os.getenv("OPENAI_API_KEY"))
        if not has_gemini and not has_openai:
            logger.warning(
                "No GEMINI_API_KEY or OPENAI_API_KEY found in environment. "
                "Running in deterministic mode (--skip-llm). "
                "Set an API key to enable LLM synthesis."
            )
            skip_llm = True
        else:
            provider = "Gemini" if has_gemini else "OpenAI"
            logger.info("LLM enabled: %s", provider)

    print("\n" + "═" * 60)
    print("  AI Lead Intelligence & Qualification Engine")
    print("  Cybersecurity Consulting Prospect Pipeline")
    print("═" * 60)
    print(f"  Config:     {config_path.name}")
    print(f"  Output dir: {output_dir}")
    print(f"  LLM:        {'disabled (--skip-llm)' if skip_llm else 'enabled'}")
    print(f"  Seed data:  {seed_path}")
    print("═" * 60 + "\n")

    # ── Step 1: Discovery ─────────────────────────────────────────────────────
    print("Step 1/5 — Lead Discovery")
    companies = discover(config, seed_path)
    print(f"  ✓ {len(companies)} companies matched targeting criteria\n")

    if not companies:
        logger.error("No companies matched the configured filters. Check config.yaml.")
        return 1

    if args.dry_run:
        print("Dry run: stopping after discovery (no enrichment or output files).")
        for c in companies:
            print(f"  • {c['company']} ({c['industry']}, {c['employee_count_raw']})")
        return 0

    # ── Step 2: Enrichment ────────────────────────────────────────────────────
    print("Step 2/5 — Company Research & Enrichment")
    skip_website = args.skip_website_check
    if skip_website:
        print("  (website reachability checks skipped)")
    enriched_list: List[Dict[str, Any]] = []
    for i, company in enumerate(companies, 1):
        _progress(i, len(companies), company.get("company", "")[:35])
        enriched = enrich(company, skip_website_check=skip_website)
        enriched_list.append(enriched)
    print(f"  ✓ {len(enriched_list)} companies enriched\n")

    # ── Step 3: Scoring ───────────────────────────────────────────────────────
    print("Step 3/5 — Deterministic Scoring")
    scored_list: List[Dict[str, Any]] = []
    for enriched in enriched_list:
        scored = score(enriched, config)
        scored_list.append(scored)

    high = sum(1 for s in scored_list if s["priority"] == "High Priority")
    medium = sum(1 for s in scored_list if s["priority"] == "Medium Priority")
    low = sum(1 for s in scored_list if s["priority"] == "Low Priority")
    avg = round(sum(s["opportunity_score"] for s in scored_list) / len(scored_list), 1)
    print(f"  ✓ Scoring complete: High={high}  Medium={medium}  Low={low}  Avg={avg}/100\n")

    # ── Step 4: LLM Analysis ──────────────────────────────────────────────────
    print(f"Step 4/5 — {'LLM Structured Analysis' if not skip_llm else 'Deterministic Analysis (LLM disabled)'}")
    analysed_list: List[Dict[str, Any]] = []
    llm_success = 0
    llm_fallback = 0
    for i, scored in enumerate(scored_list, 1):
        _progress(i, len(scored_list), scored.get("company", "")[:35])
        analysed = analyse(scored, config, skip_llm=skip_llm)
        analysed_list.append(analysed)
        if analysed.get("llm_used"):
            llm_success += 1
        elif analysed.get("pipeline_status") == "llm_fallback":
            llm_fallback += 1
    print(
        f"  ✓ Analysis complete: LLM={llm_success}  "
        f"Deterministic stub={len(analysed_list) - llm_success}"
        + (f"  Fallbacks={llm_fallback}" if llm_fallback else "")
        + "\n"
    )

    # ── Step 5: Validation ────────────────────────────────────────────────────
    print("Step 5/5 — Pydantic Schema Validation")
    valid_records, review_queue = validate_batch(analysed_list)
    print(f"  ✓ Valid: {len(valid_records)}  Review queue: {len(review_queue)}\n")

    if review_queue:
        print("  ⚠ Review queue items:")
        for item in review_queue:
            errors = [e.get("msg", "") for e in item.get("validation_errors", [])]
            print(f"    • {item.get('company','?')}: {'; '.join(errors[:2])}")
        print()

    # ── Output ────────────────────────────────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)
    metadata = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "config_file": str(config_path.name),
        "total_discovered": len(companies),
        "total_enriched": len(enriched_list),
        "total_scored": len(scored_list),
        "total_valid": len(valid_records),
        "total_review_queue": len(review_queue),
        "llm_used_count": llm_success,
        "llm_fallback_count": llm_fallback,
        "skip_llm": skip_llm,
        "scoring_thresholds": config.get("scoring", {}),
        "targeting": config.get("target", {}),
    }

    print("Writing output files…")
    write_all(valid_records, review_queue, metadata, output_dir)

    print("\n" + "═" * 60)
    print("  Pipeline complete!")
    print(f"  Elapsed:       {elapsed}s")
    print(f"  Leads output:  {output_dir / 'leads_output.csv'}")
    print(f"  Full JSON:     {output_dir / 'leads_output.json'}")
    print(f"  Dashboard:     {output_dir / 'dashboard.html'}")
    if review_queue:
        print(f"  Review queue:  {output_dir / 'review_queue.json'}")
    print("═" * 60 + "\n")

    return 0


# ── Validate-only mode ─────────────────────────────────────────────────────────

def run_validate_only(args: argparse.Namespace) -> int:
    """Validate an existing leads_output.json against the current schema."""
    logger = logging.getLogger("main")
    output_dir = ROOT / args.output_dir
    json_path = output_dir / "leads_output.json"

    if not json_path.exists():
        logger.error("No leads_output.json found at %s", json_path)
        return 1

    with json_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    leads_raw = data.get("leads", [])
    logger.info("Validating %d records from %s", len(leads_raw), json_path)
    valid, review = validate_batch(leads_raw)
    print(f"\nValidation: {len(valid)} passed, {len(review)} failed\n")
    for item in review:
        errors = [e.get("msg", "") for e in item.get("validation_errors", [])]
        print(f"  ✗ {item.get('company','?')}: {'; '.join(errors[:3])}")
    return 0 if not review else 1


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="AI-Powered Lead Intelligence & Qualification Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                          run full pipeline
  python main.py --skip-llm              deterministic only (no API key needed)
  python main.py --config custom.yaml    use custom targeting config
  python main.py --output-dir ./results  write output to ./results/
  python main.py --dry-run               discovery only, no files written
  python main.py --validate-only         re-validate existing leads_output.json
  python main.py --skip-website-check    skip HTTP website reachability check
  python main.py --verbose               enable debug logging

environment variables:
  GEMINI_API_KEY    Google Gemini API key (enables LLM synthesis)
  OPENAI_API_KEY    OpenAI API key (fallback if no Gemini key)
        """,
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to targeting config YAML (default: config.yaml)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output files (default: output/)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM analysis; use deterministic stubs only",
    )
    parser.add_argument(
        "--skip-website-check",
        action="store_true",
        help="Skip HTTP website reachability checks (faster, offline)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run discovery and print matches only — no files written",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Re-validate an existing leads_output.json and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    _setup_logging(args.verbose)

    if args.validate_only:
        sys.exit(run_validate_only(args))
    else:
        sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
