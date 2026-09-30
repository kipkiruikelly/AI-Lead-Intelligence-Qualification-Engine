"""
pipeline/validator.py
─────────────────────
Step 5 — Validation Gate

Validates enriched and analyzed company records against Pydantic LeadRecord.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.lead_schema import (
    DecisionMaker,
    DiscoveryProvenance,
    EvidenceStatus,
    LeadRecord,
    Priority,
    QualificationStatus,
    SizeBand,
)

logger = logging.getLogger(__name__)


def _coerce_record(data: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    coerced = dict(data)
    now_iso = datetime.now(timezone.utc).isoformat()

    coerced["run_id"] = run_id

    # Size
    size_raw = str(coerced.get("company_size", "Unknown")).strip()
    valid_sizes = {e.value for e in SizeBand}
    if size_raw not in valid_sizes:
        coerced["company_size"] = "Unknown"

    # Priority
    priority_raw = str(coerced.get("priority", "Low Priority")).strip()
    valid_priorities = {e.value for e in Priority}
    if priority_raw not in valid_priorities:
        coerced["priority"] = "Low Priority"

    # Qualification Status
    qs_raw = str(coerced.get("qualification_status", "Needs Review")).strip()
    valid_qs = {e.value for e in QualificationStatus}
    if qs_raw not in valid_qs:
        coerced["qualification_status"] = "Needs Review"

    # Score breakdown
    sb = coerced.get("score_breakdown", {})
    if not isinstance(sb, dict):
        sb = {}
    coerced["score_breakdown"] = {
        "size_score": int(sb.get("size_score", 0)),
        "sector_score": int(sb.get("sector_score", 0)),
        "exposure_score": int(sb.get("exposure_score", 0)),
        "complexity_score": int(sb.get("complexity_score", 0)),
        "regulatory_score": int(sb.get("regulatory_score", 0)),
        "bonus_score": int(sb.get("bonus_score", 0)),
        "total": int(sb.get("total", 0)),
    }

    coerced["opportunity_score"] = coerced["score_breakdown"]["total"]

    # Provenance
    prov = coerced.get("provenance")
    if not prov or not isinstance(prov, dict):
        coerced["provenance"] = {
            "discovery_source": str(coerced.get("discovery_source", "web_search")),
            "discovery_query": str(coerced.get("discovery_query", "target_search")),
            "source_url": str(coerced.get("source_url", coerced.get("website", ""))),
            "discovered_at": str(coerced.get("discovered_at") or now_iso),
            "raw_source_reference": str(coerced.get("raw_source_reference") or "system_coercion"),
        }
    else:
        if not prov.get("discovered_at"):
            prov["discovered_at"] = now_iso
        coerced["provenance"] = prov

    # Decision maker
    dm = coerced.get("decision_maker", {})
    if not isinstance(dm, dict):
        dm = {}
    dm.setdefault("name", "Not verified")
    dm.setdefault("title", "Not verified")

    # Hallucination Guard: If name is not 'Not verified' but verification_status is Verified without source evidence, reset to Unknown/Not verified
    v_conf = dm.get("verification_status", dm.get("confidence", "Unknown"))

    has_verified_dm_evidence = any(
        e.get("evidence_status") == "Verified" and "decision maker" in e.get("claim", "").lower()
        for e in coerced.get("source_evidence", [])
    )

    if dm["name"] != "Not verified" and v_conf == "Verified" and not has_verified_dm_evidence:
        dm["verification_status"] = "Unknown"

    dm["verification_status"] = dm["verification_status"] if dm["verification_status"] in {e.value for e in EvidenceStatus} else "Unknown"
    coerced["decision_maker"] = dm

    # Source evidence
    raw_ev = coerced.get("source_evidence", [])
    cleaned_ev = []
    for item in raw_ev:
        if isinstance(item, dict):
            ev_conf = item.get("evidence_status", "Unknown")
            if ev_conf not in {e.value for e in EvidenceStatus}:
                ev_conf = "Unknown"
            cleaned_ev.append({
                "claim": str(item.get("claim", ""))[:500],
                "url": str(item.get("url", "")),
                "source_type": str(item.get("source_type", "company_website")),
                "retrieved_at": str(item.get("retrieved_at") or now_iso),
                "evidence_text": item.get("evidence_text"),
                "evidence_status": ev_conf,
            })
    coerced["source_evidence"] = cleaned_ev

    # Observations
    obs = coerced.get("business_observations", [])
    if isinstance(obs, str):
        obs = [obs]
    coerced["business_observations"] = [str(o) for o in obs if o]

    # Outreach message
    msg = str(coerced.get("outreach_message", ""))
    msg = msg.replace("{first_name}", "[Contact]").replace("{company_name}", coerced.get("company", ""))
    coerced["outreach_message"] = msg

    # Required strings
    for field in ("description", "qualification_explanation", "website", "location", "industry"):
        coerced.setdefault(field, "Not available")

    coerced["llm_used"] = bool(coerced.get("llm_used", False))
    coerced.setdefault("pipeline_status", "ok")

    return coerced


def validate(data: Dict[str, Any], run_id: str) -> Tuple[LeadRecord | None, Dict[str, Any] | None]:
    try:
        coerced = _coerce_record(data, run_id)
        record = LeadRecord(**coerced)
        return record, None
    except ValidationError as exc:
        error_info = {
            "company": data.get("company", "Unknown"),
            "validation_errors": exc.errors(),
            "raw_data_keys": list(data.keys()),
        }
        logger.warning("Validation failed for '%s': %d error(s)", data.get("company", "Unknown"), len(exc.errors()))
        return None, error_info
    except Exception as exc:
        error_info = {
            "company": data.get("company", "Unknown"),
            "validation_errors": [{"msg": str(exc)}],
            "raw_data_keys": list(data.keys()),
        }
        logger.error("Unexpected validation error for '%s': %s", data.get("company", "Unknown"), exc)
        return None, error_info


def validate_batch(records: List[Dict[str, Any]], run_id: str) -> Tuple[List[LeadRecord], List[Dict[str, Any]]]:
    valid: List[LeadRecord] = []
    review: List[Dict[str, Any]] = []

    for data in records:
        record, error = validate(data, run_id)
        if record is not None:
            valid.append(record)
        else:
            review.append(error)

    logger.info("Validation: %d passed, %d sent to review queue", len(valid), len(review))
    return valid, review
