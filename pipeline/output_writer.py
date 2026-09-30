"""
pipeline/output_writer.py
─────────────────────────
Step 10 — Output Writer

Writes run artifacts to versioned folder structure:
  output/runs/<run_id>/
  output/latest/ (copy of latest run)
"""

from __future__ import annotations

import csv
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List

from schemas.lead_schema import LeadRecord

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "run_id", "company", "website", "industry", "location", "company_size",
    "opportunity_score", "priority", "qualification_status",
    "qualification_explanation", "business_observations",
    "decision_maker_name", "decision_maker_title", "decision_maker_verification",
    "recommended_role", "outreach_message",
    "exposure_signals", "regulatory_signals",
    "size_score", "sector_score", "exposure_score",
    "complexity_score", "regulatory_score", "bonus_score",
    "website_reachable", "llm_used", "pipeline_status",
    "discovery_source", "discovery_query", "source_url",
]


def _flatten_for_csv(record: LeadRecord) -> Dict[str, Any]:
    dm = record.decision_maker
    sb = record.score_breakdown
    prov = record.provenance
    return {
        "run_id": record.run_id,
        "company": record.company,
        "website": record.website,
        "industry": record.industry,
        "location": record.location,
        "company_size": record.company_size.value,
        "opportunity_score": record.opportunity_score,
        "priority": record.priority.value,
        "qualification_status": record.qualification_status.value,
        "qualification_explanation": record.qualification_explanation,
        "business_observations": " | ".join(record.business_observations),
        "decision_maker_name": dm.name,
        "decision_maker_title": dm.title,
        "decision_maker_verification": dm.verification_status.value,
        "recommended_role": dm.recommended_role or "",
        "outreach_message": record.outreach_message,
        "exposure_signals": " | ".join(record.exposure_signals),
        "regulatory_signals": " | ".join(record.regulatory_signals),
        "size_score": sb.size_score,
        "sector_score": sb.sector_score,
        "exposure_score": sb.exposure_score,
        "complexity_score": sb.complexity_score,
        "regulatory_score": sb.regulatory_score,
        "bonus_score": sb.bonus_score,
        "website_reachable": record.website_reachable,
        "llm_used": record.llm_used,
        "pipeline_status": record.pipeline_status,
        "discovery_source": prov.discovery_source if prov else "",
        "discovery_query": prov.discovery_query if prov else "",
        "source_url": prov.source_url if prov else record.website,
    }


def write_all(
    records: List[LeadRecord],
    review_queue: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    output_dir: Path,
) -> None:
    run_id = metadata.get("run_id", "run_unknown")
    run_folder = output_dir / "runs" / run_id
    latest_folder = output_dir / "latest"

    run_folder.mkdir(parents=True, exist_ok=True)
    latest_folder.mkdir(parents=True, exist_ok=True)

    # 1. CSV
    rows = [_flatten_for_csv(r) for r in records]
    csv_path = run_folder / "leads_output.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # 2. JSON
    json_path = run_folder / "leads_output.json"
    payload = {
        "run_metadata": metadata,
        "leads": [r.model_dump() for r in records],
        "review_queue": review_queue,
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    # 3. HTML Dashboard
    html_path = run_folder / "dashboard.html"
    _write_html_dashboard(records, review_queue, metadata, html_path)

    # 4. Review Queue / Errors
    if review_queue:
        err_path = run_folder / "review_queue.json"
        err_path.write_text(json.dumps({"review_queue": review_queue}, indent=2, default=str), encoding="utf-8")

    # Copy to latest
    for f in run_folder.iterdir():
        if f.is_file():
            shutil.copy2(f, latest_folder / f.name)

    logger.info("Output writer: Saved run %s to %s and updated %s", run_id, run_folder, latest_folder)


def _write_html_dashboard(records: List[LeadRecord], review_queue: List[Dict[str, Any]], metadata: Dict[str, Any], path: Path) -> None:
    # Simplified HTML generation writing to path
    total = len(records)
    high = sum(1 for r in records if r.priority.value == "High Priority")
    med = sum(1 for r in records if r.priority.value == "Medium Priority")
    low = sum(1 for r in records if r.priority.value == "Low Priority")

    html = f"""<!DOCTYPE html>
<html>
<head><title>Run Dashboard {metadata.get('run_id')}</title>
<style>
body {{ font-family: system-ui, sans-serif; background: #f6f8fa; margin: 20px; color: #24292f; }}
.card {{ background: white; border: 1px solid #d0d7de; padding: 15px; border-radius: 6px; margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
th, td {{ padding: 8px 12px; border: 1px solid #d0d7de; text-align: left; font-size: 13px; }}
th {{ background: #f6f8fa; }}
.badge {{ padding: 2px 6px; border-radius: 10px; font-weight: bold; font-size: 11px; }}
.high {{ background: #dafbe1; color: #1a7f37; }}
.med {{ background: #fef3c7; color: #9a6700; }}
.low {{ background: #f6f8fa; color: #6e7781; }}
</style>
</head>
<body>
<div class="card">
  <h2>🔐 Lead Qualification Dashboard — Run: {metadata.get('run_id')}</h2>
  <p><strong>Total Discovered:</strong> {metadata.get('total_discovered')} | <strong>Total Scored:</strong> {total} | <strong>High:</strong> {high} | <strong>Medium:</strong> {med} | <strong>Low:</strong> {low}</p>
  <p><strong>Discovery Provider:</strong> {metadata.get('discovery_provider')} | <strong>Timestamp:</strong> {metadata.get('run_timestamp')}</p>
</div>
<table>
<thead><tr><th>Company</th><th>Industry</th><th>Score</th><th>Priority</th><th>Status</th><th>Outreach Preview</th></tr></thead>
<tbody>
"""
    for r in records:
        badge_cls = "high" if "High" in r.priority.value else "med" if "Medium" in r.priority.value else "low"
        html += f"""<tr>
<td><a href="{r.website}" target="_blank"><strong>{r.company}</strong></a></td>
<td>{r.industry}</td>
<td><strong>{r.opportunity_score}</strong></td>
<td><span class="badge {badge_cls}">{r.priority.value}</span></td>
<td>{r.qualification_status.value}</td>
<td style="font-size:11px">{r.outreach_message[:120]}...</td>
</tr>"""

    html += "</tbody></table></body></html>"
    path.write_text(html, encoding="utf-8")
