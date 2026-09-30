"""
pipeline/output_writer.py
─────────────────────────
Step 10 — Structured Output

Writes pipeline results to three output formats:
  1. leads_output.csv   — flat structured CSV for easy review
  2. leads_output.json  — full JSON including evidence arrays
  3. dashboard.html     — self-contained HTML dashboard (no external deps)
  4. review_queue.json  — records that failed validation

The HTML dashboard includes:
  - Colour-coded priority badges
  - Sortable columns
  - Live search / filter box
  - Score breakdown tooltip
  - Collapsible outreach message
  - Evidence status tags
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from schemas.lead_schema import LeadRecord

logger = logging.getLogger(__name__)


# ─── CSV ──────────────────────────────────────────────────────────────────────

CSV_FIELDS = [
    "company", "website", "industry", "location", "company_size",
    "opportunity_score", "priority", "qualification_status",
    "qualification_explanation", "business_observations",
    "decision_maker_name", "decision_maker_title", "decision_maker_confidence",
    "recommended_role", "outreach_message",
    "exposure_signals", "regulatory_signals",
    "size_score", "sector_score", "exposure_score",
    "complexity_score", "regulatory_score", "bonus_score",
    "website_reachable", "llm_used", "pipeline_status",
    "source_urls",
]


def _flatten_for_csv(record: LeadRecord) -> Dict[str, Any]:
    dm = record.decision_maker
    sb = record.score_breakdown
    return {
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
        "decision_maker_confidence": dm.confidence.value,
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
        "source_urls": " | ".join(
            e.url for e in record.source_evidence if e.url
        ),
    }


def write_csv(records: List[LeadRecord], path: Path) -> None:
    rows = [_flatten_for_csv(r) for r in records]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    logger.info("CSV written: %s (%d rows)", path, len(rows))


# ─── JSON ─────────────────────────────────────────────────────────────────────

def write_json(
    records: List[LeadRecord],
    review_queue: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    path: Path,
) -> None:
    payload = {
        "run_metadata": metadata,
        "leads": [r.model_dump() for r in records],
        "review_queue": review_queue,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    logger.info("JSON written: %s", path)


# ─── HTML Dashboard ────────────────────────────────────────────────────────────

_PRIORITY_COLOURS = {
    "High Priority": ("#1a7f37", "#dafbe1"),
    "Medium Priority": ("#9a6700", "#fef3c7"),
    "Low Priority": ("#6e7781", "#f6f8fa"),
}

_STATUS_COLOURS = {
    "Qualified": ("#1a7f37", "#dafbe1"),
    "Needs Review": ("#9a6700", "#fef3c7"),
    "Disqualified": ("#cf222e", "#ffebe9"),
}


def _badge(text: str, colour_map: Dict) -> str:
    fg, bg = colour_map.get(text, ("#6e7781", "#f6f8fa"))
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:12px;font-size:11px;font-weight:600;'
        f'white-space:nowrap">{text}</span>'
    )


def _score_bar(score: int) -> str:
    colour = "#1a7f37" if score >= 70 else "#9a6700" if score >= 50 else "#6e7781"
    return (
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<div style="flex:1;background:#e8eaed;border-radius:4px;height:8px">'
        f'<div style="width:{score}%;background:{colour};height:8px;border-radius:4px"></div>'
        f'</div>'
        f'<span style="font-weight:700;color:{colour};min-width:30px">{score}</span>'
        f'</div>'
    )


def _evidence_tags(record: LeadRecord) -> str:
    tags = []
    counts = {"Verified": 0, "Inferred": 0, "Unknown": 0}
    for ev in record.source_evidence:
        counts[ev.evidence_status.value] = counts.get(ev.evidence_status.value, 0) + 1
    colours = {"Verified": ("#1a7f37", "#dafbe1"), "Inferred": ("#9a6700", "#fef3c7"), "Unknown": ("#6e7781", "#f6f8fa")}
    for status, count in counts.items():
        if count:
            fg, bg = colours[status]
            tags.append(
                f'<span style="background:{bg};color:{fg};padding:1px 6px;'
                f'border-radius:10px;font-size:10px">{status}: {count}</span>'
            )
    return " ".join(tags)


def _row_html(record: LeadRecord, idx: int) -> str:
    dm = record.decision_maker
    sb = record.score_breakdown
    breakdown_tip = (
        f"Size: {sb.size_score} | Sector: {sb.sector_score} | "
        f"Exposure: {sb.exposure_score} | Complexity: {sb.complexity_score} | "
        f"Regulatory: {sb.regulatory_score} | Bonus: {sb.bonus_score}"
    )
    observations_html = "".join(
        f"<li>{o}</li>" for o in record.business_observations
    ) or "<li>No observations recorded</li>"

    llm_tag = (
        '<span style="color:#0969da;font-size:10px">LLM ✓</span>'
        if record.llm_used
        else '<span style="color:#6e7781;font-size:10px">Deterministic</span>'
    )
    website_tag = (
        "✅" if record.website_reachable
        else "❌" if record.website_reachable is False
        else "—"
    )

    return f"""
    <tr class="lead-row" data-priority="{record.priority.value}" data-search="{record.company.lower()} {record.industry.lower()} {record.location.lower()}">
      <td style="font-weight:600;color:#0969da">
        <a href="{record.website}" target="_blank" rel="noopener" style="color:#0969da;text-decoration:none">{record.company}</a>
        <div style="font-size:10px;color:#6e7781;margin-top:2px">{record.location} {website_tag}</div>
      </td>
      <td style="font-size:12px;color:#24292f">{record.industry}</td>
      <td style="text-align:center">{record.company_size.value}</td>
      <td title="{breakdown_tip} | TOTAL: {record.opportunity_score}">{_score_bar(record.opportunity_score)}</td>
      <td>{_badge(record.priority.value, _PRIORITY_COLOURS)}</td>
      <td>{_badge(record.qualification_status.value, _STATUS_COLOURS)}</td>
      <td style="font-size:11px;max-width:200px">
        <div style="font-weight:600">{dm.name}</div>
        <div style="color:#6e7781">{dm.recommended_role or dm.title}</div>
        <div style="font-size:10px;color:#9a6700">{dm.confidence.value}</div>
      </td>
      <td>
        <details>
          <summary style="cursor:pointer;font-size:11px;color:#0969da">View explanation</summary>
          <div style="font-size:11px;margin-top:4px;color:#24292f">{record.qualification_explanation}</div>
          <ul style="font-size:11px;margin:4px 0 0 0;padding-left:16px">{observations_html}</ul>
        </details>
      </td>
      <td style="font-size:11px;max-width:250px">
        <details>
          <summary style="cursor:pointer;color:#0969da;font-size:11px">View message</summary>
          <div style="font-size:11px;margin-top:4px;background:#f6f8fa;padding:8px;border-radius:4px;border-left:3px solid #0969da">{record.outreach_message}</div>
        </details>
      </td>
      <td style="font-size:10px">{_evidence_tags(record)}<div style="margin-top:2px">{llm_tag}</div></td>
    </tr>"""


def write_html(
    records: List[LeadRecord],
    review_queue: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    path: Path,
) -> None:
    run_time = metadata.get("run_timestamp", datetime.now(timezone.utc).isoformat())
    total = len(records)
    high = sum(1 for r in records if r.priority.value == "High Priority")
    medium = sum(1 for r in records if r.priority.value == "Medium Priority")
    low = sum(1 for r in records if r.priority.value == "Low Priority")
    avg_score = round(sum(r.opportunity_score for r in records) / total, 1) if total else 0
    llm_count = sum(1 for r in records if r.llm_used)

    rows_html = "\n".join(_row_html(r, i) for i, r in enumerate(records))

    review_rows = ""
    for item in review_queue:
        errors = "; ".join(
            str(e.get("msg", "")) for e in item.get("validation_errors", [])
        )
        review_rows += f"<tr><td>{item.get('company','?')}</td><td style='color:#cf222e;font-size:11px'>{errors}</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Lead Intelligence — Cybersecurity Consulting</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
          background: #f6f8fa; color: #24292f; font-size: 13px; }}
  .header {{ background: #0d1117; color: #e6edf3; padding: 24px 32px; }}
  .header h1 {{ font-size: 20px; font-weight: 700; }}
  .header .sub {{ color: #8b949e; font-size: 12px; margin-top: 4px; }}
  .stats {{ display: flex; gap: 16px; padding: 16px 32px; background: #fff;
            border-bottom: 1px solid #d0d7de; flex-wrap: wrap; }}
  .stat {{ background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px;
           padding: 12px 20px; text-align: center; min-width: 100px; }}
  .stat .val {{ font-size: 24px; font-weight: 700; color: #0969da; }}
  .stat .lbl {{ font-size: 11px; color: #6e7781; margin-top: 2px; }}
  .controls {{ padding: 12px 32px; background: #fff; border-bottom: 1px solid #d0d7de;
               display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
  .controls input {{ padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 6px;
                     font-size: 13px; width: 260px; }}
  .controls select {{ padding: 6px 10px; border: 1px solid #d0d7de; border-radius: 6px; font-size: 13px; }}
  .controls label {{ font-size: 12px; color: #6e7781; }}
  .table-wrap {{ padding: 16px 32px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border: 1px solid #d0d7de; border-radius: 8px; overflow: hidden; }}
  th {{ background: #f6f8fa; padding: 10px 12px; text-align: left; font-size: 11px;
        font-weight: 600; color: #6e7781; text-transform: uppercase; letter-spacing: 0.5px;
        border-bottom: 1px solid #d0d7de; cursor: pointer; user-select: none; white-space: nowrap; }}
  th:hover {{ background: #e8eaed; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #f6f8fa; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f6f8fa; }}
  details summary {{ list-style: none; }}
  details summary::-webkit-details-marker {{ display: none; }}
  .section-title {{ padding: 16px 32px 8px; font-weight: 700; font-size: 14px; color: #0d1117; }}
  .review-table {{ margin: 0 32px 32px; background: #fff; border: 1px solid #d0d7de;
                   border-radius: 8px; overflow: hidden; }}
  .review-table th {{ background: #ffebe9; color: #cf222e; }}
  .footer {{ padding: 16px 32px; color: #6e7781; font-size: 11px; border-top: 1px solid #d0d7de; }}
  .hidden {{ display: none; }}
  @media (max-width: 768px) {{ .stats {{ gap: 8px; }} .table-wrap {{ padding: 8px; }} }}
</style>
</head>
<body>

<div class="header">
  <h1>🔐 AI Lead Intelligence &amp; Qualification Engine</h1>
  <div class="sub">Cybersecurity Consulting Prospects · Generated {run_time} · {total} leads processed</div>
</div>

<div class="stats">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Total Leads</div></div>
  <div class="stat"><div class="val" style="color:#1a7f37">{high}</div><div class="lbl">High Priority</div></div>
  <div class="stat"><div class="val" style="color:#9a6700">{medium}</div><div class="lbl">Medium Priority</div></div>
  <div class="stat"><div class="val" style="color:#6e7781">{low}</div><div class="lbl">Low Priority</div></div>
  <div class="stat"><div class="val">{avg_score}</div><div class="lbl">Avg Score</div></div>
  <div class="stat"><div class="val" style="color:#0969da">{llm_count}</div><div class="lbl">LLM Analysed</div></div>
  <div class="stat"><div class="val" style="color:#cf222e">{len(review_queue)}</div><div class="lbl">Review Queue</div></div>
</div>

<div class="controls">
  <label>Search:</label>
  <input type="text" id="search" placeholder="Company, industry, location…" oninput="filterTable()">
  <label>Priority:</label>
  <select id="priorityFilter" onchange="filterTable()">
    <option value="">All priorities</option>
    <option value="High Priority">High Priority</option>
    <option value="Medium Priority">Medium Priority</option>
    <option value="Low Priority">Low Priority</option>
  </select>
  <label>Min score:</label>
  <input type="number" id="minScore" placeholder="0" min="0" max="100" style="width:70px" oninput="filterTable()">
</div>

<div class="table-wrap">
<table id="leadsTable">
  <thead>
    <tr>
      <th onclick="sortTable(0)">Company ↕</th>
      <th onclick="sortTable(1)">Industry ↕</th>
      <th onclick="sortTable(2)">Size ↕</th>
      <th onclick="sortTable(3)">Score ↕</th>
      <th onclick="sortTable(4)">Priority ↕</th>
      <th onclick="sortTable(5)">Status ↕</th>
      <th>Decision Maker</th>
      <th>Qualification</th>
      <th>Outreach</th>
      <th>Evidence</th>
    </tr>
  </thead>
  <tbody id="tableBody">
    {rows_html}
  </tbody>
</table>
</div>

{"" if not review_queue else f'''
<div class="section-title">⚠️ Review Queue ({len(review_queue)} items)</div>
<table class="review-table">
  <thead><tr><th>Company</th><th>Validation Error</th></tr></thead>
  <tbody>{review_rows}</tbody>
</table>
'''}

<div class="footer">
  <strong>Data reliability:</strong> All company information sourced from public profiles and websites.
  Evidence is tagged Verified / Inferred / Unknown. Opportunity signals are prospecting hypotheses —
  not findings that a company has a security weakness. Decision-maker names marked "Not verified" were
  not confirmed in public sources. · Pipeline: {metadata.get("config_file","config.yaml")} ·
  Scoring: fully deterministic (no LLM) · Outreach: {"LLM-generated" if llm_count else "deterministic stub"}
</div>

<script>
let sortDir = {{}};

function filterTable() {{
  const search = document.getElementById("search").value.toLowerCase();
  const priority = document.getElementById("priorityFilter").value;
  const minScore = parseInt(document.getElementById("minScore").value) || 0;
  const rows = document.querySelectorAll("#tableBody .lead-row");
  rows.forEach(row => {{
    const matchSearch = !search || row.dataset.search.includes(search);
    const matchPriority = !priority || row.dataset.priority === priority;
    const scoreEl = row.querySelector("td:nth-child(4) span[style*='font-weight:700']");
    const score = scoreEl ? parseInt(scoreEl.textContent) : 0;
    const matchScore = score >= minScore;
    row.classList.toggle("hidden", !(matchSearch && matchPriority && matchScore));
  }});
}}

function sortTable(col) {{
  const tbody = document.getElementById("tableBody");
  const rows = Array.from(tbody.querySelectorAll(".lead-row"));
  sortDir[col] = !sortDir[col];
  rows.sort((a, b) => {{
    const aVal = a.querySelectorAll("td")[col]?.textContent.trim() || "";
    const bVal = b.querySelectorAll("td")[col]?.textContent.trim() || "";
    const aNum = parseFloat(aVal); const bNum = parseFloat(bVal);
    if (!isNaN(aNum) && !isNaN(bNum)) return sortDir[col] ? aNum - bNum : bNum - aNum;
    return sortDir[col] ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")
    logger.info("HTML dashboard written: %s", path)


# ─── Review queue JSON ────────────────────────────────────────────────────────

def write_review_queue(items: List[Dict[str, Any]], path: Path) -> None:
    path.write_text(
        json.dumps({"review_queue": items, "count": len(items)}, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info("Review queue written: %s (%d items)", path, len(items))


# ─── Main entry point ─────────────────────────────────────────────────────────

def write_all(
    records: List[LeadRecord],
    review_queue: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(records, output_dir / "leads_output.csv")
    write_json(records, review_queue, metadata, output_dir / "leads_output.json")
    write_html(records, review_queue, metadata, output_dir / "dashboard.html")
    if review_queue:
        write_review_queue(review_queue, output_dir / "review_queue.json")
    logger.info("All outputs written to: %s", output_dir)
